"""Identificação 1:N: melhor score por pessoa, limiar e margem entre pessoas parecidas."""
import numpy as np
import pytest

from core import galeria, matcher


def unit(*xs):
    v = np.zeros(512, np.float32); v[: len(xs)] = xs
    return v / np.linalg.norm(v)


@pytest.fixture
def galeria_falsa(monkeypatch):
    def montar(itens):  # [(usuario_id, vetor), ...]
        ids = np.array([u for u, _ in itens], np.int64)
        m = np.stack([v for _, v in itens]).astype(np.float32)
        monkeypatch.setattr(galeria, "instantaneo", lambda: (ids, m))
    return montar


def test_galeria_vazia(galeria_falsa, monkeypatch):
    monkeypatch.setattr(galeria, "instantaneo", lambda: (np.empty(0), np.empty((0, 512))))
    assert matcher.identificar(unit(1)) == (None, 0.0)


def test_identifica_acima_do_limiar(galeria_falsa):
    galeria_falsa([(1, unit(1, 0)), (2, unit(0, 1))])
    uid, s = matcher.identificar(unit(1, 0.1))
    assert uid == 1 and s > 0.9


def test_abaixo_do_limiar_nao_identifica(galeria_falsa):
    galeria_falsa([(1, unit(1, 0, 0)), (2, unit(0, 1, 0))])
    assert matcher.identificar(unit(0.3, 0.2, 1))[0] is None


def test_varias_fotos_da_mesma_pessoa_nao_contam_como_rival(galeria_falsa):
    """Duas fotos quase iguais da pessoa 1 não podem 'empatar' entre si e derrubar a identificação."""
    galeria_falsa([(1, unit(1, 0)), (1, unit(1, 0.02)), (2, unit(0, 1))])
    assert matcher.identificar(unit(1, 0.01))[0] == 1


def test_duas_pessoas_muito_parecidas_nao_identifica(galeria_falsa):
    galeria_falsa([(1, unit(1, 0.10)), (2, unit(1, 0.12))])
    uid, s = matcher.identificar(unit(1, 0.11))
    assert uid is None and s > 0.9


def test_ranking_por_pessoa(galeria_falsa):
    galeria_falsa([(2, unit(0, 1)), (1, unit(1, 0)), (1, unit(0.9, 0.1))])
    assert [u for u, _ in matcher.ranking(unit(1, 0))] == [1, 2]


def test_parecido_com_ignora_a_propria_pessoa(galeria_falsa):
    galeria_falsa([(1, unit(1, 0)), (2, unit(0, 1))])
    assert matcher.parecido_com(unit(1, 0))[0] == 1
    assert matcher.parecido_com(unit(1, 0), ignorar=1)[0] is None


def test_menor_similaridade_entre_fotos():
    i, j, s = matcher.menor_similaridade_entre([unit(1, 0), unit(1, 0.05), unit(0, 1)])
    assert (i, j) in {(1, 3), (2, 3)} and s < 0.1
    assert matcher.menor_similaridade_entre([unit(1)]) is None
