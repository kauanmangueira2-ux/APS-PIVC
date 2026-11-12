"""Fluxo completo de uma tentativa de acesso — o que o terminal do cofre dispara.

 1 bloqueio?  2 recurso  3 imagem -> vetor  4 identificação  5 autorização
 6 (nível 3) prova de vida + PIN  7 registro em log (com evidência se negado)
"""
import logging
from datetime import datetime

import config
from core import auditoria, matcher, permissoes, seguranca
from db import repositorio
from visao import embedding, liveness
from visao.captura import ErroVisao, decodificar

log = logging.getLogger("cofre.fluxo")

MENSAGENS = {
    "concedido": "Acesso concedido.",
    "negado_nivel": "Nível de permissão insuficiente para este recurso.",
    "negado_divisao": "Este recurso pertence a outra divisão.",
    "negado_horario": "Fora do horário de expediente (08h–18h).",
    "nao_reconhecido": "Pessoa não reconhecida.",
    "falha_liveness": "Prova de vida falhou. Pisque olhando para a câmera, sozinho no enquadramento.",
    "pin_invalido": "PIN inválido.",
    "pin_bloqueado": "PIN bloqueado por excesso de tentativas. Aguarde alguns minutos ou procure o administrador.",
}


def _mesma_pessoa(quadros: list, usuario_id: int) -> bool:
    """A prova de vida só vale se o rosto que pisca é o mesmo que foi identificado.
    Confere alguns quadros da rajada; quadros em que não há rosto utilizável (olhos
    fechados, borrão) são ignorados, mas qualquer outra pessoa identificada reprova."""
    n = config.QUADROS_CONFERIDOS_NIVEL3
    passo = max(1, len(quadros) // n)
    for q in quadros[passo::passo][: max(n - 1, 0)]:
        try:
            outro, _ = matcher.identificar(embedding.extrair(q).vetor)
        except ErroVisao:
            continue
        if outro != usuario_id:
            return False
    return True


def _resposta(resultado, usuario=None, score=0.0, evidencia=None):
    return {
        "concedido": resultado == "concedido",
        "resultado": resultado,
        "mensagem": MENSAGENS[resultado],
        "usuario": usuario["nome"] if usuario else None,
        "nivel": usuario["nivel"] if usuario else None,
        "score": round(score, 4),
        "evidencia": evidencia,
    }


def tentar_acesso(imagens: list, recurso_id: int, pin: str = "", agora=None):
    """`imagens`: bytes de 1+ quadros (vários quadros alimentam a prova de vida).
    Levanta ErroVisao para falhas que não são tentativa de acesso (sem rosto, câmera...)."""
    agora = agora or datetime.now()

    restante = auditoria.segundos_de_bloqueio()
    if restante:
        raise ErroVisao("terminal_bloqueado", f"Terminal bloqueado por tentativas negadas. Aguarde {restante}s.",
                        segundos=restante)

    recurso = repositorio.obter_recurso(recurso_id)
    if not recurso:
        raise ErroVisao("recurso_invalido", "Recurso não encontrado.")
    if not imagens:
        raise ErroVisao("imagem_invalida", "Nenhuma imagem recebida.")

    quadros = [decodificar(b) for b in imagens]
    principal = quadros[0]
    vetor = embedding.extrair(principal).vetor

    usuario_id, score = matcher.identificar(vetor)
    if usuario_id is None:
        ev = auditoria.registrar(None, recurso, "nao_reconhecido", score, principal)
        return _resposta("nao_reconhecido", score=score, evidencia=ev)

    usuario = repositorio.obter_usuario(usuario_id)
    ok, motivo = permissoes.autorizar(usuario, recurso, agora)

    if ok and permissoes.exige_segundo_fator(recurso):
        try:
            vivo = liveness.piscou(quadros) and _mesma_pessoa(quadros, usuario_id)
        except Exception:  # falha no MediaPipe: o cofre mais sensível não abre (e o erro vai para o log)
            log.exception("Prova de vida indisponível; acesso ao cofre negado por segurança")
            vivo = False
        if not vivo:
            ok, motivo = False, "falha_liveness"
        elif repositorio.pins_invalidos_recentes(usuario_id, config.PIN_JANELA_MIN) >= config.PIN_TENTATIVAS_MAX:
            ok, motivo = False, "pin_bloqueado"   # nem confere o PIN: impede adivinhar por tentativa e erro
        elif not seguranca.pin_valido(pin, usuario["pin_hash"]):
            ok, motivo = False, "pin_invalido"
        elif seguranca.precisa_atualizar(usuario["pin_hash"]):
            try:  # hash antigo: regrava no formato novo (melhor esforço)
                repositorio.atualizar_usuario(usuario_id, {"pin_hash": seguranca.hash_pin(pin)})
            except Exception:
                log.exception("Não foi possível atualizar o hash do PIN do usuário %s", usuario_id)

    ev = auditoria.registrar(usuario_id, recurso, motivo, score, None if ok else principal)
    return _resposta(motivo, usuario, score, ev)
