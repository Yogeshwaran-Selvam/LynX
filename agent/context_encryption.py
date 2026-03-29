"""
Fernet-based encryption for LynX context storage.
Derives key from Django's SECRET_KEY — no extra key files needed.
"""

import base64
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


_fernet_cache = None


def _get_fernet() -> Fernet:
    global _fernet_cache
    if _fernet_cache is None:
        from django.conf import settings
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"lynx-local-context",
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
        _fernet_cache = Fernet(key)
    return _fernet_cache


def encrypt_json(data: dict) -> bytes:
    """Encrypt a dict as JSON → Fernet bytes."""
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return _get_fernet().encrypt(plaintext)


def decrypt_json(token: bytes) -> dict:
    """Decrypt Fernet bytes → JSON dict."""
    plaintext = _get_fernet().decrypt(token)
    return json.loads(plaintext.decode("utf-8"))
