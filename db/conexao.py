"""Pool de conexões MySQL e gerenciador de cursor."""
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

import config

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="cofre", pool_size=5, charset="utf8mb4", **config.DB
        )
    return _pool


@contextmanager
def cursor(commit=False):
    """Entrega um cursor de dicionários; devolve a conexão ao pool no fim — SEMPRE.

    O cursor é "buffered": o resultado vem inteiro do servidor, então fechar o cursor sem ler
    tudo não dá erro. Sem isso, um SELECT não lido fazia o close() falhar ("Unread result
    found"), a conexão nunca voltava ao pool e, após 5 vezes, o pool esgotava e o sistema
    inteiro passava a responder "banco indisponível"."""
    conn = _get_pool().get_connection()
    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()   # devolve ao pool mesmo se algo acima falhar


def banco_disponivel() -> bool:
    try:
        with cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchall()
        return True
    except mysql.connector.Error:
        return False
