from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from backend.app.core.config import settings


class SecretsCipher:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode("utf-8"))

    def encrypt_str(self, value: str) -> str:
        if value is None:
            raise ValueError("value is None")
        token = self._fernet.encrypt(value.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt_str(self, token: str) -> str:
        try:
            value = self._fernet.decrypt(token.encode("utf-8"))
        except InvalidToken as e:
            raise ValueError("Invalid secret token") from e
        return value.decode("utf-8")


secrets_cipher = SecretsCipher(settings.secrets_fernet_key)
