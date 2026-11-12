"""A conexão sempre volta ao pool (regressão do pool esgotado por cursor não lido)."""
import mysql.connector
import pytest

from db import conexao


class CursorFalso:
    def __init__(self, falha_ao_fechar=False):
        self.falha_ao_fechar = falha_ao_fechar

    def execute(self, *a):
        pass

    def fetchall(self):
        return [{"1": 1}]

    def close(self):
        if self.falha_ao_fechar:
            raise mysql.connector.errors.InternalError("Unread result found")


class ConexaoFalsa:
    def __init__(self, cur):
        self.cur, self.fechada, self.kwargs = cur, False, None

    def cursor(self, **kwargs):
        self.kwargs = kwargs
        return self.cur

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.fechada = True


@pytest.fixture
def pool(monkeypatch):
    conexoes = []

    def nova(falha=False):
        c = ConexaoFalsa(CursorFalso(falha))
        conexoes.append(c)
        monkeypatch.setattr(conexao, "_get_pool", lambda: type("P", (), {"get_connection": lambda self: c})())
        return c
    return nova


def test_cursor_e_buffered_e_devolve_conexao(pool):
    c = pool()
    with conexao.cursor() as cur:
        cur.execute("SELECT 1")
    assert c.kwargs == {"dictionary": True, "buffered": True} and c.fechada


def test_conexao_volta_ao_pool_mesmo_se_fechar_cursor_falhar(pool):
    c = pool(falha=True)
    with pytest.raises(mysql.connector.Error):
        with conexao.cursor() as cur:
            cur.execute("SELECT 1")
    assert c.fechada


def test_conexao_volta_ao_pool_quando_a_consulta_falha(pool):
    c = pool()
    with pytest.raises(RuntimeError):
        with conexao.cursor():
            raise RuntimeError("falha na consulta")
    assert c.fechada


def test_banco_disponivel(pool):
    c = pool()
    assert conexao.banco_disponivel() and c.fechada
