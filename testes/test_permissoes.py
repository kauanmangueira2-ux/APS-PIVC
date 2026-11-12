from datetime import datetime

from core.permissoes import autorizar, exige_segundo_fator

DIV_A, DIV_B = 1, 2
ANTESSALA = {"nivel_minimo": 1, "divisao_id": None}
ACERVO_A = {"nivel_minimo": 2, "divisao_id": DIV_A}
COFRE = {"nivel_minimo": 3, "divisao_id": None}

HORA_UTIL = datetime(2026, 10, 14, 10, 0)
MADRUGADA = datetime(2026, 10, 14, 2, 0)


def usuario(nivel, divisao=None, ativo=True):
    return {"nivel": nivel, "divisao_id": divisao, "ativo": ativo}


def test_nivel1_entra_na_antessala():
    assert autorizar(usuario(1), ANTESSALA, HORA_UTIL) == (True, "concedido")


def test_nivel1_negado_no_cofre_principal():
    assert autorizar(usuario(1), COFRE, HORA_UTIL) == (False, "negado_nivel")


def test_nivel2_acessa_a_propria_divisao():
    assert autorizar(usuario(2, DIV_A), ACERVO_A, HORA_UTIL) == (True, "concedido")


def test_nivel2_negado_em_outra_divisao():
    assert autorizar(usuario(2, DIV_B), ACERVO_A, HORA_UTIL) == (False, "negado_divisao")


def test_nivel2_bloqueado_fora_do_expediente_no_acervo():
    assert autorizar(usuario(2, DIV_A), ACERVO_A, MADRUGADA) == (False, "negado_horario")


def test_horario_vale_nos_limites_do_expediente():
    assert autorizar(usuario(2, DIV_A), ACERVO_A, datetime(2026, 10, 14, 8, 0)) == (True, "concedido")
    assert autorizar(usuario(2, DIV_A), ACERVO_A, datetime(2026, 10, 14, 17, 59)) == (True, "concedido")
    assert autorizar(usuario(2, DIV_A), ACERVO_A, datetime(2026, 10, 14, 18, 0)) == (False, "negado_horario")


def test_nivel2_entra_na_antessala_a_qualquer_hora():
    """Regressão: o horário restringe só os acervos; antessala/catálogo são abertos ao nível 1."""
    assert autorizar(usuario(2, DIV_A), ANTESSALA, MADRUGADA) == (True, "concedido")


def test_nivel3_acessa_sem_restricao_de_divisao_ou_horario():
    assert autorizar(usuario(3), ACERVO_A, MADRUGADA) == (True, "concedido")
    assert autorizar(usuario(3), COFRE, MADRUGADA) == (True, "concedido")


def test_usuario_inativo_nao_passa():
    assert autorizar(usuario(3, ativo=False), COFRE, HORA_UTIL) == (False, "nao_reconhecido")


def test_so_o_cofre_exige_segundo_fator():
    assert exige_segundo_fator(COFRE)
    assert not exige_segundo_fator(ACERVO_A)
