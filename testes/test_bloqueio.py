from core.auditoria import calcular_bloqueio

NEG, OK = "nao_reconhecido", "concedido"


def hist(*pares):  # (resultado, idade) do mais recente ao mais antigo
    return [{"resultado": r, "idade": i} for r, i in pares]


def test_tres_negativas_seguidas_bloqueiam():
    assert calcular_bloqueio(hist((NEG, 5), (NEG, 10), (NEG, 15))) == 55


def test_bloqueio_dura_60s_a_partir_da_ultima_negativa():
    assert calcular_bloqueio(hist((NEG, 30), (NEG, 40), (NEG, 50))) == 30
    assert calcular_bloqueio(hist((NEG, 60), (NEG, 70), (NEG, 80))) == 0


def test_bloqueio_expira():
    assert calcular_bloqueio(hist((NEG, 61), (NEG, 66), (NEG, 71))) == 0


def test_uma_negativa_depois_de_expirar_NAO_reabre_o_bloqueio():
    """Regressão do bug: as 2 negativas antigas + 1 nova não formam uma sequência."""
    assert calcular_bloqueio(hist((NEG, 0), (NEG, 70), (NEG, 80))) == 0
    assert calcular_bloqueio(hist((NEG, 0), (NEG, 1), (NEG, 80))) == 0


def test_nova_sequencia_depois_de_expirar_bloqueia_de_novo():
    assert calcular_bloqueio(hist((NEG, 0), (NEG, 5), (NEG, 10))) == 60


def test_acesso_concedido_no_meio_zera_a_sequencia():
    assert calcular_bloqueio(hist((NEG, 1), (OK, 5), (NEG, 9))) == 0


def test_menos_de_tres_tentativas_nao_bloqueia():
    assert calcular_bloqueio(hist((NEG, 1), (NEG, 2))) == 0
    assert calcular_bloqueio([]) == 0


def test_negativas_espalhadas_no_tempo_nao_bloqueiam():
    assert calcular_bloqueio(hist((NEG, 5), (NEG, 50), (NEG, 120))) == 0
