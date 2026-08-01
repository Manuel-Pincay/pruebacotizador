import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config.settings import settings


def _get_key() -> bytes:
    hex_key = settings.encryption_key
    if not hex_key:
        if settings.is_production:
            raise RuntimeError("ERP_ENCRYPTION_KEY es obligatoria en producción")
        hex_key = "0" * 64
    key = bytes.fromhex(hex_key)
    if len(key) != 32:
        raise ValueError("ERP_ENCRYPTION_KEY debe ser 64 caracteres hex (32 bytes)")
    return key


def generate_encryption_key() -> str:
    return secrets.token_hex(32)


def encrypt_text(plaintext: str) -> str:
    key = _get_key()
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    encrypted = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    return (iv + encrypted).hex()


def decrypt_text(ciphertext_hex: str) -> str:
    key = _get_key()
    data = bytes.fromhex(ciphertext_hex)
    iv = data[:12]
    encrypted = data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, encrypted, None).decode("utf-8")


def encrypt_bytes(data: bytes) -> bytes:
    key = _get_key()
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    encrypted = aesgcm.encrypt(iv, data, None)
    return iv + encrypted


def decrypt_bytes(data: bytes) -> bytes:
    key = _get_key()
    iv = data[:12]
    encrypted = data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, encrypted, None)
