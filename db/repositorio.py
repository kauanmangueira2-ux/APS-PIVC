"""Acesso a dados: todo SQL do sistema fica aqui."""
from db.conexao import cursor

CAMPOS_EDITAVEIS = {"nome", "cargo", "divisao_id", "nivel", "ativo", "pin_hash"}


# ---------- divisões e recursos ----------
def listar_divisoes():
    with cursor() as cur:
        cur.execute("SELECT id, nome FROM divisoes ORDER BY nome")
        return cur.fetchall()


def listar_recursos():
    with cursor() as cur:
        cur.execute("SELECT id, nome, nivel_minimo, divisao_id FROM recursos ORDER BY nivel_minimo, nome")
        return cur.fetchall()


def obter_recurso(recurso_id):
    with cursor() as cur:
        cur.execute("SELECT id, nome, nivel_minimo, divisao_id FROM recursos WHERE id=%s", (recurso_id,))
        return cur.fetchone()


# ---------- usuários ----------
def criar_usuario(nome, matricula, cargo, divisao_id, nivel, pin_hash=None):
    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO usuarios (nome, matricula, cargo, divisao_id, nivel, pin_hash) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (nome, matricula, cargo, divisao_id, nivel, pin_hash),
        )
        return cur.lastrowid


def obter_usuario(usuario_id):
    with cursor() as cur:
        cur.execute(
            "SELECT u.*, d.nome AS divisao FROM usuarios u "
            "LEFT JOIN divisoes d ON d.id=u.divisao_id WHERE u.id=%s",
            (usuario_id,),
        )
        return cur.fetchone()


def listar_usuarios():
    with cursor() as cur:
        cur.execute(
            "SELECT u.id, u.nome, u.matricula, u.cargo, u.divisao_id, d.nome AS divisao, "
            "u.nivel, u.ativo, (u.pin_hash IS NOT NULL) AS tem_pin, "
            "(SELECT COUNT(*) FROM biometrias b WHERE b.usuario_id=u.id) AS biometrias "
            "FROM usuarios u LEFT JOIN divisoes d ON d.id=u.divisao_id ORDER BY u.nome"
        )
        return cur.fetchall()


def atualizar_usuario(usuario_id, campos: dict):
    campos = {k: v for k, v in campos.items() if k in CAMPOS_EDITAVEIS}
    if not campos:
        return False
    sql = ", ".join(f"{k}=%s" for k in campos)
    with cursor(commit=True) as cur:
        cur.execute(f"UPDATE usuarios SET {sql} WHERE id=%s", (*campos.values(), usuario_id))
        return cur.rowcount > 0


def remover_usuario(usuario_id):
    with cursor(commit=True) as cur:
        cur.execute("DELETE FROM usuarios WHERE id=%s", (usuario_id,))
        return cur.rowcount > 0


# ---------- biometrias ----------
def adicionar_biometria(usuario_id, vetor_bytes, qualidade):
    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO biometrias (usuario_id, vetor, qualidade) VALUES (%s,%s,%s)",
            (usuario_id, vetor_bytes, qualidade),
        )
        return cur.lastrowid


def carregar_biometrias_ativas():
    """(usuario_id, vetor) de todos os usuários ativos — alimenta a galeria em memória."""
    with cursor() as cur:
        cur.execute(
            "SELECT b.usuario_id, b.vetor FROM biometrias b "
            "JOIN usuarios u ON u.id=b.usuario_id WHERE u.ativo=TRUE"
        )
        return cur.fetchall()


def limpar_biometrias(usuario_id):
    with cursor(commit=True) as cur:
        cur.execute("DELETE FROM biometrias WHERE usuario_id=%s", (usuario_id,))


# ---------- acessos / auditoria ----------
def registrar_acesso(usuario_id, recurso_id, resultado, score, evidencia, alerta=False):
    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO acessos (usuario_id, recurso_id, resultado, score, evidencia, alerta) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (usuario_id, recurso_id, resultado, score, evidencia, alerta),
        )
        return cur.lastrowid


def consultar_acessos(inicio=None, fim=None, usuario_id=None, resultado=None, limite=500):
    where, params = [], []
    if inicio:
        where.append("a.ocorrido_em >= %s"); params.append(inicio)
    if fim:
        where.append("a.ocorrido_em < DATE_ADD(%s, INTERVAL 1 DAY)"); params.append(fim)
    if usuario_id:
        where.append("a.usuario_id = %s"); params.append(usuario_id)
    if resultado:
        where.append("a.resultado = %s"); params.append(resultado)
    cond = ("WHERE " + " AND ".join(where)) if where else ""
    with cursor() as cur:
        cur.execute(
            "SELECT a.id, a.ocorrido_em, a.usuario_id, u.nome AS usuario, r.nome AS recurso, "
            "a.resultado, a.score, a.evidencia, a.alerta "
            f"FROM acessos a LEFT JOIN usuarios u ON u.id=a.usuario_id "
            f"LEFT JOIN recursos r ON r.id=a.recurso_id {cond} "
            "ORDER BY a.ocorrido_em DESC, a.id DESC LIMIT %s",
            (*params, limite),
        )
        return cur.fetchall()


def ultimos_resultados(n):
    """Últimos n acessos com a idade em segundos (para o bloqueio por intrusão)."""
    with cursor() as cur:
        cur.execute(
            "SELECT resultado, TIMESTAMPDIFF(SECOND, ocorrido_em, NOW()) AS idade "
            "FROM acessos ORDER BY id DESC LIMIT %s",
            (n,),
        )
        return cur.fetchall()


def alertas_recentes(minutos):
    with cursor() as cur:
        cur.execute(
            "SELECT a.id, a.ocorrido_em, u.nome AS usuario, a.resultado, a.evidencia "
            "FROM acessos a LEFT JOIN usuarios u ON u.id=a.usuario_id "
            "WHERE a.alerta=TRUE AND a.ocorrido_em >= DATE_SUB(NOW(), INTERVAL %s MINUTE) "
            "ORDER BY a.id DESC",
            (minutos,),
        )
        return cur.fetchall()


def pins_invalidos_recentes(usuario_id, minutos):
    """PINs errados da pessoa nos últimos `minutos`, contando só depois do último acesso concedido."""
    with cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM acessos WHERE usuario_id=%s AND resultado='pin_invalido' "
            "AND ocorrido_em >= DATE_SUB(NOW(), INTERVAL %s MINUTE) "
            "AND id > COALESCE((SELECT MAX(c.id) FROM acessos c WHERE c.usuario_id=%s "
            "AND c.resultado='concedido'), 0)",
            (usuario_id, minutos, usuario_id),
        )
        return int(cur.fetchone()["n"])


def resumo_do_dia():
    """Números de hoje para o painel de logs."""
    with cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(resultado='concedido'), 0) AS concedidos, "
            "COALESCE(SUM(resultado<>'concedido'), 0) AS negados, "
            "COALESCE(SUM(resultado='nao_reconhecido'), 0) AS nao_reconhecidos, "
            "COALESCE(SUM(alerta), 0) AS alertas "
            "FROM acessos WHERE ocorrido_em >= CURDATE()"
        )
        linha = cur.fetchone()
        return {k: int(v or 0) for k, v in linha.items()}
