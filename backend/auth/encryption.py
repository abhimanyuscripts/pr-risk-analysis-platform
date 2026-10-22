import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY")
if not TOKEN_ENCRYPTION_KEY:
    raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set (see backend/.env.example)")

_fernet = Fernet(TOKEN_ENCRYPTION_KEY)


def encrypt_token(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    return _fernet.decrypt(encrypted_token.encode()).decode()