import os
from cryptography.fernet import Fernet

def get_fernet():
    key = os.environ.get('FERNET_ENCRYPTION_KEY')
    if not key:
        raise ValueError("FERNET_ENCRYPTION_KEY is not set in environment.")
    return Fernet(key.encode('utf-8'))

def encrypt_value(value: str) -> bytes:
    if not value:
        return b""
    f = get_fernet()
    return f.encrypt(value.encode('utf-8'))

def decrypt_value(token: bytes) -> str:
    if not token:
        return ""
    f = get_fernet()
    # Convert memoryview to bytes (PostgreSQL BinaryField returns memoryview)
    if isinstance(token, memoryview):
        token = bytes(token)
    return f.decrypt(token).decode('utf-8')
