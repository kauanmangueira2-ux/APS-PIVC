"""Hash e verificação de PIN (segundo fator do nível 3).

Formato atual:  pbkdf2$<iterações>$<sal hex>$<hash hex>   (PBKDF2-HMAC-SHA256, sal aleatório por PIN,
mais o pepper do .env). Hashes antigos (SHA-256 puro, 64 caracteres hex) ainda são aceitos e
são trocados pelo formato novo no primeiro acesso correto (ver core/fluxo.py).
"""
import hashlib
import hmac
import secrets

import config

_PREFIXO = "pbkdf2"


def _derivar(pin: str, sal: bytes, iteracoes: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", (config.PIN_PEPPER + pin).encode(), sal, iteracoes)


def hash_pin(pin: str) -> str:
    sal = secrets.token_bytes(16)
    n = config.PIN_ITERACOES
    return f"{_PREFIXO}${n}${sal.hex()}${_derivar(pin, sal, n).hex()}"


def _hash_antigo(pin: str) -> str:
    return hashlib.sha256((config.PIN_PEPPER + pin).encode()).hexdigest()


def pin_valido(pin: str, pin_hash: str | None) -> bool:
    if not pin or not pin_hash:
        return False
    if pin_hash.startswith(_PREFIXO + "$"):
        try:
            _, n, sal, esperado = pin_hash.split("$")
            calculado = _derivar(pin, bytes.fromhex(sal), int(n)).hex()
        except ValueError:
            return False
        return hmac.compare_digest(calculado, esperado)
    return hmac.compare_digest(_hash_antigo(pin), pin_hash)


def precisa_atualizar(pin_hash: str | None) -> bool:
    """True para hash no formato antigo ou com menos iterações que o configurado."""
    if not pin_hash:
        return False
    if not pin_hash.startswith(_PREFIXO + "$"):
        return True
    try:
        return int(pin_hash.split("$")[1]) < config.PIN_ITERACOES
    except (IndexError, ValueError):
        return True


def formato_pin_ok(pin: str) -> bool:
    return len(pin) == 6 and pin.isdigit()
