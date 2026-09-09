import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

_fernet = Fernet(os.getenv("TOKEN_ENCRYPTION_KEY"))


def encrypt_token(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    return _fernet.decrypt(encrypted_token.encode()).decode()