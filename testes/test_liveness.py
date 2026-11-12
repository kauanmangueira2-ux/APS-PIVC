"""Lógica da piscada (pura: recebe a série de EARs, sem câmera nem modelo)."""
import config
from visao import liveness
from visao.liveness import contar_piscadas, detectou_piscada


def test_piscada_aberto_fechado_aberto():
    assert detectou_piscada([0.30, 0.31, 0.29, 0.12, 0.30, 0.31, 0.30])


def test_piscada_lenta_com_dois_quadros_fechados():
    assert detectou_piscada([0.30, 0.31, 0.14, 0.12, 0.29, 0.30])


def test_olhos_pequenos_tambem_funcionam():
    """Limiar relativo: EAR aberto de 0,22 também serve."""
    assert detectou_piscada([0.22, 0.23, 0.21, 0.09, 0.22, 0.23])


def test_conta_duas_piscadas():
    assert contar_piscadas([0.30, 0.12, 0.30, 0.31, 0.11, 0.30, 0.30]) == 2


def test_exigir_duas_piscadas(monkeypatch):
    monkeypatch.setattr(config, "PISCADAS_EXIGIDAS", 2)
    assert not detectou_piscada([0.30, 0.31, 0.12, 0.30, 0.31, 0.30])
    assert detectou_piscada([0.30, 0.12, 0.30, 0.31, 0.11, 0.30, 0.30])


def test_olhos_abertos_o_tempo_todo_nao_e_piscada():
    assert not detectou_piscada([0.30, 0.31, 0.29, 0.30, 0.28, 0.31, 0.30])


def test_ruido_pequeno_nao_e_piscada():
    assert not detectou_piscada([0.30, 0.27, 0.31, 0.26, 0.30, 0.28])


def test_foto_parada_nao_e_piscada():
    assert not detectou_piscada([0.298, 0.301, 0.299, 0.300, 0.302, 0.299])


def test_olhos_fechados_o_tempo_todo_nao_e_piscada():
    assert not detectou_piscada([0.10, 0.11, 0.09, 0.10, 0.12, 0.10])


def test_fechou_e_nao_reabriu_nao_conta():
    assert not detectou_piscada([0.30, 0.31, 0.30, 0.29, 0.12, 0.11])


def test_comecou_fechado_e_abriu_nao_conta():
    assert not detectou_piscada([0.12, 0.30, 0.31, 0.30, 0.29, 0.30])


def test_poucos_quadros_nao_julgam():
    assert not detectou_piscada([0.30, 0.10, 0.30])
    assert not detectou_piscada([])


def test_piscou_ignora_quadros_sem_rosto(monkeypatch):
    serie = iter([(1, 0.30), (0, None), (1, 0.31), (1, 0.29), (1, 0.11), (1, 0.30), (1, 0.31)])
    monkeypatch.setattr(liveness, "analisar_quadro", lambda q: next(serie))
    assert liveness.piscou([object()] * 7)


def test_dois_rostos_reprova_mesmo_piscando(monkeypatch):
    serie = iter([(1, 0.30), (1, 0.31), (2, 0.12), (1, 0.30), (1, 0.31), (1, 0.30)])
    monkeypatch.setattr(liveness, "analisar_quadro", lambda q: next(serie))
    assert not liveness.piscou([object()] * 6)
