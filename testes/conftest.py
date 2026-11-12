"""Infra de teste: banco em memória e reconhecimento facial simulado.

Nada aqui precisa de MySQL, InsightFace ou câmera: a "pessoa" de cada imagem é codificada na
cor da imagem, e o embedding falso devolve o vetor dessa pessoa. Assim os testes validam
as regras do sistema (fluxo, permissões, bloqueio, API) em segundos.
"""
import time

import cv2
import numpy as np
import pytest

import config
from core import galeria, seguranca
from db import repositorio
from visao import embedding, liveness

DIVISAO_A, DIVISAO_B = 10, 20
RECURSOS = {
    1: {"id": 1, "nome": "Antessala", "nivel_minimo": 1, "divisao_id": None},
    2: {"id": 2, "nome": "Acervo A", "nivel_minimo": 2, "divisao_id": DIVISAO_A},
    3: {"id": 3, "nome": "Acervo B", "nivel_minimo": 2, "divisao_id": DIVISAO_B},
    5: {"id": 5, "nome": "Cofre principal", "nivel_minimo": 3, "divisao_id": None},
}
SERVIDOR, DIRETORA, MINISTRO, DESCONHECIDO = 1, 2, 3, 9
PIN = "123456"
PIN_HASH = seguranca.hash_pin(PIN)   # calculado uma vez (PBKDF2 é propositalmente lento)


def imagem(pessoa: int, largura=64) -> bytes:
    """JPEG uniforme cuja cor identifica a pessoa."""
    a = np.full((largura, largura, 3), 40 + 20 * pessoa, np.uint8)
    return cv2.imencode(".jpg", a)[1].tobytes()


def _pessoa_da_imagem(bgr) -> int:
    return int(round((float(bgr[0, 0, 0]) - 40) / 20))


def _vetor(pessoa: int) -> np.ndarray:
    v = np.zeros(512, np.float32)
    v[pessoa] = 1.0
    return v


class Banco:
    def __init__(self):
        self.usuarios = {
            SERVIDOR: {"id": SERVIDOR, "nome": "Servidor", "nivel": 1, "divisao_id": DIVISAO_A, "ativo": True, "pin_hash": None},
            DIRETORA: {"id": DIRETORA, "nome": "Diretora", "nivel": 2, "divisao_id": DIVISAO_A, "ativo": True, "pin_hash": None},
            MINISTRO: {"id": MINISTRO, "nome": "Ministro", "nivel": 3, "divisao_id": None, "ativo": True,
                       "pin_hash": PIN_HASH},
        }
        for uid, u in self.usuarios.items():
            u["matricula"] = str(1000 * u["nivel"] + uid)
        self.acessos = []          # {"resultado", "alerta", "evidencia", "t"}
        self.deslocamento = 0.0    # "avança o relógio" sem dormir
        self.novos_usuarios = []
        self.atualizacoes = []

    def agora(self):
        return time.time() + self.deslocamento

    def avancar(self, segundos):
        self.deslocamento += segundos


@pytest.fixture
def banco(monkeypatch, tmp_path):
    b = Banco()
    monkeypatch.setattr(config, "DIR_EVIDENCIAS", tmp_path / "evidencias")

    monkeypatch.setattr(repositorio, "obter_recurso", lambda i: RECURSOS.get(i))
    monkeypatch.setattr(repositorio, "listar_recursos", lambda: list(RECURSOS.values()))
    monkeypatch.setattr(repositorio, "obter_usuario", lambda i: b.usuarios.get(i))
    monkeypatch.setattr(repositorio, "carregar_biometrias_ativas", lambda: [
        {"usuario_id": u, "vetor": embedding.para_bytes(_vetor(u))} for u in b.usuarios if b.usuarios[u]["ativo"]])

    def registrar(uid, rid, resultado, score, evidencia, alerta=False):
        b.acessos.append({"usuario_id": uid, "recurso_id": rid, "resultado": resultado,
                          "alerta": alerta, "evidencia": evidencia, "t": b.agora()})
    monkeypatch.setattr(repositorio, "registrar_acesso", registrar)
    monkeypatch.setattr(repositorio, "ultimos_resultados", lambda n: [
        {"resultado": a["resultado"], "idade": b.agora() - a["t"]} for a in b.acessos[::-1][:n]])

    def criar(nome, matricula, cargo, divisao_id, nivel, pin_hash=None):
        b.novos_usuarios.append((nome, matricula, nivel, divisao_id))
        return 100 + len(b.novos_usuarios)
    monkeypatch.setattr(repositorio, "criar_usuario", criar)
    monkeypatch.setattr(repositorio, "adicionar_biometria", lambda *a, **k: 1)

    def atualizar(uid, campos):
        b.usuarios[uid].update(campos)
        b.atualizacoes.append((uid, dict(campos)))
        return True
    monkeypatch.setattr(repositorio, "atualizar_usuario", atualizar)

    def pins_invalidos(uid, minutos):
        n = 0
        for a in reversed(b.acessos):
            if a["usuario_id"] != uid:
                continue
            if a["resultado"] == "concedido" or b.agora() - a["t"] > minutos * 60:
                break
            n += a["resultado"] == "pin_invalido"
        return n
    monkeypatch.setattr(repositorio, "pins_invalidos_recentes", pins_invalidos)
    monkeypatch.setattr(repositorio, "resumo_do_dia", lambda: {
        "total": len(b.acessos), "concedidos": sum(a["resultado"] == "concedido" for a in b.acessos),
        "negados": sum(a["resultado"] != "concedido" for a in b.acessos),
        "nao_reconhecidos": sum(a["resultado"] == "nao_reconhecido" for a in b.acessos),
        "alertas": sum(bool(a["alerta"]) for a in b.acessos)})

    def extrair(bgr):
        pessoa = _pessoa_da_imagem(bgr)
        # pessoas sem cadastro também têm rosto próprio (vetor distinto), fora da galeria
        return type("R", (), {"vetor": _vetor(pessoa if pessoa in b.usuarios else 100 + pessoa),
                              "qualidade": 0.99, "bbox": (10.0, 10.0, 130.0, 150.0)})()
    monkeypatch.setattr(embedding, "extrair", extrair)
    monkeypatch.setattr(liveness, "piscou", lambda quadros: True)
    galeria.recarregar()
    return b


@pytest.fixture(autouse=True)
def _zera_limite_de_token():
    """O limite de tentativas do token de admin é por IP e guardado em memória: zera entre testes."""
    from api import app as api_app
    api_app._falhas_admin.clear()
    yield
    api_app._falhas_admin.clear()
