"""Rotas da API com banco em memória (sem MySQL nem InsightFace)."""
import pytest
from fastapi.testclient import TestClient

import config
from api import app as api_app
from testes.conftest import MINISTRO, SERVIDOR, imagem

ADMIN = {"X-Admin-Token": config.ADMIN_TOKEN}
NOVA, OUTRA = 5, 6          # pessoas sem cadastro


@pytest.fixture
def cliente(banco, monkeypatch):
    monkeypatch.setattr(api_app, "banco_disponivel", lambda: True)
    monkeypatch.setattr(api_app.liveness, "disponivel", lambda: True)
    monkeypatch.setattr(api_app.repositorio, "consultar_acessos", lambda *a, **k: [
        {"ocorrido_em": "2026-11-09 10:00:00", "usuario": "Ministro", "recurso": "Cofre", "resultado": "concedido", "score": 0.91},
        {"ocorrido_em": "2026-11-09 10:05:00", "usuario": None, "recurso": "Cofre", "resultado": "nao_reconhecido", "score": None},
    ])
    return TestClient(api_app.app)


def foto(pessoa, nome="f.jpg"):
    return ("fotos", (nome, imagem(pessoa), "image/jpeg"))


def quadro(pessoa):
    return ("imagens", ("q.jpg", imagem(pessoa), "image/jpeg"))


# ---------- terminal ----------
def test_saude(cliente):
    r = cliente.get("/api/saude").json()
    assert r["banco"] is True and r["prova_de_vida"] is True and "segredos_padrao" in r


def test_recursos_publicos(cliente):
    assert {x["nome"] for x in cliente.get("/api/recursos").json()} >= {"Antessala", "Cofre principal"}


def test_reconhecer_concede(cliente):
    r = cliente.post("/api/reconhecer", data={"recurso_id": 1}, files=[quadro(SERVIDOR)])
    assert r.status_code == 200 and r.json()["concedido"] is True


def test_reconhecer_imagem_invalida(cliente):
    r = cliente.post("/api/reconhecer", data={"recurso_id": 1}, files=[("imagens", ("a.jpg", b"lixo", "image/jpeg"))])
    assert r.status_code == 422 and r.json()["erro"] == "imagem_invalida"


def test_reconhecer_cofre_exige_pin(cliente):
    r = cliente.post("/api/reconhecer", data={"recurso_id": 5, "pin": "000000"}, files=[quadro(MINISTRO)] * 15)
    assert r.json()["resultado"] == "pin_invalido"


def test_terminal_bloqueado_informa_segundos(cliente):
    for _ in range(3):
        cliente.post("/api/reconhecer", data={"recurso_id": 1}, files=[quadro(9)])
    r = cliente.post("/api/reconhecer", data={"recurso_id": 1}, files=[quadro(SERVIDOR)])
    corpo = r.json()
    assert r.status_code == 422 and corpo["erro"] == "terminal_bloqueado" and 0 < corpo["segundos"] <= 60


def test_limite_de_imagens_por_envio(cliente):
    r = cliente.post("/api/reconhecer", data={"recurso_id": 1}, files=[quadro(SERVIDOR)] * (config.MAX_IMAGENS_POR_ENVIO + 1))
    assert r.status_code == 422


def test_limite_de_tamanho_da_imagem(cliente, monkeypatch):
    monkeypatch.setattr(config, "MAX_BYTES_POR_IMAGEM", 100)
    r = cliente.post("/api/reconhecer", data={"recurso_id": 1}, files=[quadro(SERVIDOR)])
    assert r.status_code == 413


def test_cabecalhos_de_seguranca(cliente):
    h = cliente.get("/api/recursos").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in h["content-security-policy"] and h["cache-control"] == "no-store"
    assert "content-security-policy" in cliente.get("/").headers


# ---------- token de administrador ----------
def test_rotas_admin_exigem_token(cliente):
    assert cliente.get("/api/usuarios").status_code == 401
    assert cliente.get("/api/usuarios", headers={"X-Admin-Token": "errado"}).status_code == 401
    assert cliente.get("/api/admin/verificar", headers=ADMIN).status_code == 200


def test_muitos_tokens_errados_bloqueiam_o_ip(cliente):
    for _ in range(config.ADMIN_FALHAS_MAX):
        assert cliente.get("/api/admin/verificar", headers={"X-Admin-Token": "chute"}).status_code == 401
    assert cliente.get("/api/admin/verificar", headers={"X-Admin-Token": "chute"}).status_code == 429
    # nem o token certo passa enquanto a janela não termina (impede força bruta)
    assert cliente.get("/api/admin/verificar", headers=ADMIN).status_code == 429


def test_token_certo_zera_as_falhas(cliente):
    for _ in range(config.ADMIN_FALHAS_MAX - 1):
        cliente.get("/api/admin/verificar", headers={"X-Admin-Token": "chute"})
    assert cliente.get("/api/admin/verificar", headers=ADMIN).status_code == 200
    assert cliente.get("/api/admin/verificar", headers={"X-Admin-Token": "chute"}).status_code == 401


# ---------- evidências ----------
def test_evidencia_so_com_token_no_cabecalho(cliente):
    config.DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    (config.DIR_EVIDENCIAS / "x.jpg").write_bytes(imagem(1))
    assert cliente.get("/api/evidencia/x.jpg").status_code == 401
    assert cliente.get("/api/evidencia/x.jpg", params={"token": config.ADMIN_TOKEN}).status_code == 401  # na URL não vale mais
    r = cliente.get("/api/evidencia/x.jpg", headers=ADMIN)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_evidencia_bloqueia_path_traversal(cliente):
    assert cliente.get("/api/evidencia/..%2f..%2fconfig.py", headers=ADMIN).status_code == 404


# ---------- cadastro ----------
def dados(**extra):
    return {"nome": "Nova Pessoa", "matricula": "77", "nivel": 1, **extra}


def test_cadastro_ok(cliente, banco):
    r = cliente.post("/api/usuarios", headers=ADMIN, data=dados(nome=" Ana ", matricula=" 55 "), files=[foto(NOVA)] * 3)
    assert r.status_code == 201 and r.json()["biometrias"] == 3
    assert banco.novos_usuarios[-1][:2] == ("Ana", "55")


def test_cadastro_exige_3_a_5_fotos(cliente):
    assert cliente.post("/api/usuarios", headers=ADMIN, data=dados(), files=[foto(NOVA)] * 2).status_code == 422
    assert cliente.post("/api/usuarios", headers=ADMIN, data=dados(), files=[foto(NOVA)] * 6).status_code == 422


def test_cadastro_valida_nivel_2_sem_divisao(cliente):
    r = cliente.post("/api/usuarios", headers=ADMIN, data=dados(nivel=2, divisao_id=""), files=[foto(NOVA)] * 3)
    assert r.status_code == 422 and "divisão" in r.json()["detail"]


def test_cadastro_valida_pin_do_nivel_3(cliente):
    r = cliente.post("/api/usuarios", headers=ADMIN, data=dados(nivel=3, pin="12"), files=[foto(NOVA)] * 3)
    assert r.status_code == 422


def test_cadastro_aponta_a_foto_ruim(cliente):
    r = cliente.post("/api/usuarios", headers=ADMIN, data=dados(),
                     files=[foto(NOVA), ("fotos", ("f.jpg", b"lixo", "image/jpeg")), foto(NOVA)])
    assert r.status_code == 422 and r.json()["mensagem"].startswith("Foto 2:")


def test_cadastro_recusa_fotos_de_pessoas_diferentes(cliente, banco):
    r = cliente.post("/api/usuarios", headers=ADMIN, data=dados(), files=[foto(NOVA), foto(NOVA), foto(OUTRA)])
    assert r.status_code == 422 and "não parecem ser da mesma pessoa" in r.json()["detail"]
    assert not banco.novos_usuarios


def test_cadastro_recusa_rosto_ja_cadastrado(cliente, banco):
    r = cliente.post("/api/usuarios", headers=ADMIN, data=dados(), files=[foto(SERVIDOR)] * 3)
    assert r.status_code == 409 and "já está cadastrado como Servidor" in r.json()["detail"]
    assert not banco.novos_usuarios


def test_adicionar_fotos_da_propria_pessoa(cliente):
    r = cliente.post(f"/api/usuarios/{SERVIDOR}/biometrias", headers=ADMIN, files=[foto(SERVIDOR)] * 2)
    assert r.status_code == 201


def test_adicionar_fotos_de_outra_pessoa_e_recusado(cliente):
    r = cliente.post(f"/api/usuarios/{SERVIDOR}/biometrias", headers=ADMIN, files=[foto(NOVA)])
    assert r.status_code == 422 and "não parece ser de Servidor" in r.json()["detail"]
    r = cliente.post(f"/api/usuarios/{SERVIDOR}/biometrias", headers=ADMIN, files=[foto(MINISTRO)])
    assert r.status_code == 409


def test_qualidade_da_foto(cliente):
    def uma(pessoa):
        return [("foto", ("f.jpg", imagem(pessoa), "image/jpeg"))]
    ok = cliente.post("/api/qualidade", headers=ADMIN, files=uma(NOVA)).json()
    assert ok["ok"] and ok["ja_cadastrado"] is None and ok["largura_rosto"] == 120
    dup = cliente.post("/api/qualidade", headers=ADMIN, files=uma(MINISTRO)).json()
    assert dup["ja_cadastrado"].startswith("Ministro")
    ruim = cliente.post("/api/qualidade", headers=ADMIN, files=[("foto", ("f.jpg", b"lixo", "image/jpeg"))])
    assert ruim.status_code == 422


def test_editar_pin_grava_hash_novo(cliente, banco):
    r = cliente.put(f"/api/usuarios/{MINISTRO}", headers=ADMIN, json={"pin": "654321"})
    assert r.status_code == 200 and banco.usuarios[MINISTRO]["pin_hash"].startswith("pbkdf2$")


# ---------- logs ----------
def test_resumo_do_dia(cliente):
    cliente.post("/api/reconhecer", data={"recurso_id": 1}, files=[quadro(SERVIDOR)])
    cliente.post("/api/reconhecer", data={"recurso_id": 5}, files=[quadro(9)])
    r = cliente.get("/api/resumo", headers=ADMIN).json()
    assert r == {"total": 2, "concedidos": 1, "negados": 1, "nao_reconhecidos": 1, "alertas": 1}


def test_exportar_csv_com_rotulos_e_bom(cliente):
    r = cliente.get("/api/logs/exportar?formato=csv", headers=ADMIN)
    assert r.status_code == 200 and r.content.startswith("﻿".encode())
    texto = r.content.decode("utf-8-sig")
    assert "Concedido" in texto and "Não reconhecido" in texto and "— não reconhecido —" in texto


def test_exportar_pdf_e_formato_invalido(cliente):
    assert cliente.get("/api/logs/exportar?formato=pdf", headers=ADMIN).content[:5] == b"%PDF-"
    assert cliente.get("/api/logs/exportar?formato=xml", headers=ADMIN).status_code == 422
