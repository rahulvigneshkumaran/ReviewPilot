import base64
import os
from datetime import datetime, timedelta
from typing import Any, Union, Optional
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

# --- JWT helpers ---

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token for user sessions."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """Decode a JWT access token and return its payload."""
    try:
        decoded_token = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        return decoded_token
    except jwt.PyJWTError:
        return {}

# --- Token Encryption helpers (AES-256-GCM) ---

def encrypt_token(token: str) -> str:
    """Encrypt a sensitive string (like a GitHub OAuth token) using AES-256-GCM."""
    if not token:
        return ""
    
    # Base64 decode the encryption key from settings (must be 32 bytes)
    try:
        key = base64.b64decode(settings.ENCRYPTION_KEY)
    except Exception:
        # Fallback for dev / mock testing if the key is not valid base64
        key = settings.ENCRYPTION_KEY.encode()[:32].rjust(32, b'\0')
        
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # GCM standard 12-byte nonce
    ciphertext = aesgcm.encrypt(nonce, token.encode("utf-8"), None)
    
    # Store nonce and ciphertext together, base64 encoded
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode("utf-8")

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an encrypted token using AES-256-GCM."""
    if not encrypted_token:
        return ""
    
    try:
        key = base64.b64decode(settings.ENCRYPTION_KEY)
    except Exception:
        key = settings.ENCRYPTION_KEY.encode()[:32].rjust(32, b'\0')
        
    combined = base64.b64decode(encrypted_token.encode("utf-8"))
    if len(combined) < 12:
        raise ValueError("Invalid encrypted token payload")
        
    nonce = combined[:12]
    ciphertext = combined[12:]
    
    aesgcm = AESGCM(key)
    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")
