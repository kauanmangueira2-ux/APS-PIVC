"""Registro de tentativas, evidência fotográfica e bloqueio por intrusão."""
import logging
from datetime import datetime

import cv2

import config
from db import repositorio

log = logging.getLogger("cofre.auditoria")


def salvar_evidencia(bgr, rotulo: str) -> str:
    config.DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    nome = f"{datetime.now():%Y%m%d_%H%M%S_%f}_{rotulo}.jpg"
    cv2.imwrite(str(config.DIR_EVIDENCIAS / nome), bgr)
    return f"dados/evidencias/{nome}"


def registrar(usuario_id, recurso, resultado, score, quadro=None):
    """Grava a tentativa. Toda negativa leva o quadro como evidência; negativa em
    recurso de nível 3 também marca alerta para o painel do admin."""
    negado = resultado != "concedido"
    evidencia = salvar_evidencia(quadro, resultado) if negado and quadro is not None else None
    alerta = negado and recurso is not None and recurso["nivel_minimo"] >= 3
    if alerta:
        log.warning("ALERTA: tentativa negada (%s) no recurso '%s'", resultado, recurso["nome"])
    repositorio.registrar_acesso(
        usuario_id, recurso["id"] if recurso else None, resultado, score, evidencia, alerta
    )
    return evidencia


def calcular_bloqueio(ultimas: list, n: int = None, janela: int = None, duracao: int = None) -> int:
    """Segundos de bloqueio restantes, dado o histórico (do mais recente ao mais antigo).

    Bloqueia quando as últimas `n` tentativas foram todas negadas E aconteceram dentro de
    `janela` segundos uma da outra. O bloqueio dura `duracao` segundos a partir da última
    negativa. Depois que expira, é preciso uma nova sequência de `n` negativas para travar de
    novo (uma única negativa não reabre o bloqueio).
    Cada item de `ultimas` tem `resultado` e `idade` (segundos desde a tentativa)."""
    n = config.NEGATIVAS_PARA_BLOQUEIO if n is None else n
    janela = config.JANELA_NEGATIVAS_SEGUNDOS if janela is None else janela
    duracao = config.BLOQUEIO_SEGUNDOS if duracao is None else duracao
    if len(ultimas) < n:
        return 0
    ultimas = ultimas[:n]
    if any(u["resultado"] == "concedido" for u in ultimas):
        return 0
    idades = [int(u["idade"]) for u in ultimas]
    if max(idades) - min(idades) > janela:       # negativas espalhadas: não é uma sequência
        return 0
    return max(duracao - min(idades), 0)


def segundos_de_bloqueio() -> int:
    """Consulta o histórico no banco e devolve o tempo de bloqueio restante (0 = liberado)."""
    return calcular_bloqueio(repositorio.ultimos_resultados(config.NEGATIVAS_PARA_BLOQUEIO))
