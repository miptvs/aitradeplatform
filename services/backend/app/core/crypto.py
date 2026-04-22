from cryptography.fernet import Fernet

from app.core.config import get_settings

settings = get_settings()
fernet = Fernet(settings.app_encryption_key.encode())


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return fernet.encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    return fernet.decrypt(value.encode()).decode()
