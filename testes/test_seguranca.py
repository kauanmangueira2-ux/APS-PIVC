"""Hash do PIN: PBKDF2 com sal e compatibilidade com o hash antigo."""
import hashlib

import config
from core import seguranca


def test_hash_novo_tem_formato_e_sal():
    a, b = seguranca.hash_pin("123456"), seguranca.hash_pin("123456")
    assert a.startswith("pbkdf2$") and len(a) <= 128
    assert a != b                      # sal aleatório: mesmo PIN, hashes diferentes
    assert seguranca.pin_valido("123456", a) and seguranca.pin_valido("123456", b)


def test_pin_errado_ou_vazio():
    h = seguranca.hash_pin("123456")
    assert not seguranca.pin_valido("123457", h)
    assert not seguranca.pin_valido("", h)
    assert not seguranca.pin_valido("123456", None)


def test_hash_corrompido_nao_quebra():
    assert not seguranca.pin_valido("123456", "pbkdf2$abc$zz$yy")
    assert not seguranca.pin_valido("123456", "pbkdf2$1")


def test_hash_antigo_ainda_vale_e_pede_atualizacao():
    antigo = hashlib.sha256((config.PIN_PEPPER + "123456").encode()).hexdigest()
    assert seguranca.pin_valido("123456", antigo)
    assert not seguranca.pin_valido("000000", antigo)
    assert seguranca.precisa_atualizar(antigo)
    assert not seguranca.precisa_atualizar(seguranca.hash_pin("123456"))


def test_mais_iteracoes_no_config_pede_atualizacao(monkeypatch):
    h = seguranca.hash_pin("123456")
    monkeypatch.setattr(config, "PIN_ITERACOES", config.PIN_ITERACOES * 2)
    assert seguranca.precisa_atualizar(h) and seguranca.pin_valido("123456", h)


def test_pepper_faz_parte_do_hash(monkeypatch):
    h = seguranca.hash_pin("123456")
    monkeypatch.setattr(config, "PIN_PEPPER", "outro-pepper")
    assert not seguranca.pin_valido("123456", h)


def test_formato_do_pin():
    assert seguranca.formato_pin_ok("012345")
    assert not seguranca.formato_pin_ok("12345") and not seguranca.formato_pin_ok("12345a")
