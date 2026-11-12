"""Fluxo completo de acesso (core.fluxo) com banco em memória e reconhecimento simulado."""
from datetime import datetime

import pytest

from core import fluxo
from testes.conftest import (DESCONHECIDO, DIRETORA, MINISTRO, PIN, SERVIDOR, imagem)
from visao import liveness
from visao.captura import ErroVisao

HORA_UTIL = datetime(2026, 11, 9, 10, 0)
MADRUGADA = datetime(2026, 11, 9, 2, 0)


def acessar(pessoa, recurso, pin="", agora=HORA_UTIL, quadros=1):
    return fluxo.tentar_acesso([imagem(pessoa)] * quadros, recurso, pin, agora)


def test_servidor_entra_na_antessala(banco):
    r = acessar(SERVIDOR, 1)
    assert r["concedido"] and r["usuario"] == "Servidor"


def test_servidor_no_cofre_e_negado_com_alerta_e_evidencia(banco, tmp_path):
    r = acessar(SERVIDOR, 5)
    assert r["resultado"] == "negado_nivel"
    assert banco.acessos[-1]["alerta"] is True
    assert r["evidencia"] and (tmp_path / "evidencias").exists()


def test_negativa_fora_do_cofre_nao_gera_alerta(banco):
    acessar(DESCONHECIDO, 1)
    assert banco.acessos[-1]["resultado"] == "nao_reconhecido"
    assert banco.acessos[-1]["alerta"] is False


def test_diretora_acervo_da_propria_divisao_em_horario_util(banco):
    assert acessar(DIRETORA, 2)["concedido"]


def test_diretora_outra_divisao_negada(banco):
    assert acessar(DIRETORA, 3)["resultado"] == "negado_divisao"


def test_diretora_acervo_de_madrugada_negada(banco):
    assert acessar(DIRETORA, 2, agora=MADRUGADA)["resultado"] == "negado_horario"


def test_diretora_antessala_de_madrugada_liberada(banco):
    assert acessar(DIRETORA, 1, agora=MADRUGADA)["concedido"]


def test_ministro_cofre_com_pin_e_prova_de_vida(banco):
    assert acessar(MINISTRO, 5, PIN, quadros=15)["concedido"]


def test_ministro_cofre_pin_errado(banco):
    r = acessar(MINISTRO, 5, "000000", quadros=15)
    assert r["resultado"] == "pin_invalido" and banco.acessos[-1]["alerta"]


def test_ministro_cofre_sem_pin(banco):
    assert acessar(MINISTRO, 5, "", quadros=15)["resultado"] == "pin_invalido"


def test_ministro_cofre_sem_piscar(banco, monkeypatch):
    monkeypatch.setattr(liveness, "piscou", lambda q: False)
    assert acessar(MINISTRO, 5, PIN, quadros=15)["resultado"] == "falha_liveness"


@pytest.mark.parametrize("erro", [ImportError("sem mediapipe"), AttributeError("sem solutions"), RuntimeError("falha")])
def test_falha_no_mediapipe_nega_o_cofre_e_registra(banco, monkeypatch, erro):
    """Regressão: antes, AttributeError virava erro 500 sem registro e sem alerta."""
    def quebrar(_):
        raise erro
    monkeypatch.setattr(liveness, "piscou", quebrar)
    r = acessar(MINISTRO, 5, PIN, quadros=15)
    assert r["resultado"] == "falha_liveness"
    assert banco.acessos[-1]["resultado"] == "falha_liveness" and banco.acessos[-1]["alerta"]


def test_piscada_de_outra_pessoa_nao_vale(banco):
    """O rosto do primeiro quadro é do ministro, mas quem aparece no resto da rajada é outro."""
    quadros = [imagem(MINISTRO)] + [imagem(SERVIDOR)] * 14
    r = fluxo.tentar_acesso(quadros, 5, PIN, HORA_UTIL)
    assert r["resultado"] == "falha_liveness"


def test_rajada_so_do_ministro_passa(banco):
    assert fluxo.tentar_acesso([imagem(MINISTRO)] * 15, 5, PIN, HORA_UTIL)["concedido"]


def test_recurso_inexistente(banco):
    with pytest.raises(ErroVisao) as e:
        acessar(SERVIDOR, 99)
    assert e.value.codigo == "recurso_invalido"


def test_sem_imagens(banco):
    with pytest.raises(ErroVisao) as e:
        fluxo.tentar_acesso([], 1, "", HORA_UTIL)
    assert e.value.codigo == "imagem_invalida"


def test_tres_negativas_bloqueiam_o_terminal_ate_para_quem_tem_acesso(banco):
    for _ in range(3):
        acessar(DESCONHECIDO, 1)
    with pytest.raises(ErroVisao) as e:
        acessar(SERVIDOR, 1)
    assert e.value.codigo == "terminal_bloqueado"


def test_apos_o_bloqueio_uma_negativa_nao_trava_de_novo(banco):
    """Regressão do bug do bloqueio reaberto por uma única negativa."""
    for _ in range(3):
        acessar(DESCONHECIDO, 1)
    banco.avancar(61)
    assert acessar(DESCONHECIDO, 1)["resultado"] == "nao_reconhecido"
    assert acessar(SERVIDOR, 1)["concedido"]


def test_acesso_concedido_zera_a_contagem(banco):
    acessar(DESCONHECIDO, 1); acessar(DESCONHECIDO, 1)
    assert acessar(SERVIDOR, 1)["concedido"]
    acessar(DESCONHECIDO, 1); acessar(DESCONHECIDO, 1)
    assert acessar(SERVIDOR, 1)["concedido"]


def errar_pin_devagar(banco, vezes):
    """Erra o PIN espaçando as tentativas (31 s) para não cair no bloqueio geral do terminal,
    como faria alguém tentando adivinhar com calma."""
    for _ in range(vezes):
        assert acessar(MINISTRO, 5, "000000", quadros=15)["resultado"] == "pin_invalido"
        banco.avancar(31)


def test_pin_bloqueia_apos_3_erros_mesmo_com_pin_certo(banco):
    errar_pin_devagar(banco, 3)
    r = acessar(MINISTRO, 5, PIN, quadros=15)
    assert r["resultado"] == "pin_bloqueado" and banco.acessos[-1]["alerta"]


def test_pin_desbloqueia_depois_da_janela(banco):
    import config
    errar_pin_devagar(banco, 3)
    banco.avancar(config.PIN_JANELA_MIN * 60 + 1)
    assert acessar(MINISTRO, 5, PIN, quadros=15)["concedido"]


def test_acesso_certo_zera_a_contagem_de_pin(banco):
    errar_pin_devagar(banco, 2)
    assert acessar(MINISTRO, 5, PIN, quadros=15)["concedido"]
    errar_pin_devagar(banco, 2)
    assert acessar(MINISTRO, 5, PIN, quadros=15)["concedido"]


def test_hash_antigo_do_pin_e_atualizado_no_acesso(banco):
    import hashlib
    import config
    banco.usuarios[MINISTRO]["pin_hash"] = hashlib.sha256((config.PIN_PEPPER + PIN).encode()).hexdigest()
    assert acessar(MINISTRO, 5, PIN, quadros=15)["concedido"]
    assert banco.atualizacoes and banco.usuarios[MINISTRO]["pin_hash"].startswith("pbkdf2$")
