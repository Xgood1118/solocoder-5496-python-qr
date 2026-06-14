import hashlib
import base64
import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

ENCRYPT_PREFIX = 'QRENC:'

def derive_key(secret: str, salt: str = 'qr-service-salt') -> bytes:
    return hashlib.pbkdf2_hmac('sha256', secret.encode('utf-8'), salt.encode('utf-8'), 100000, dklen=32)

def encrypt_content(content: str, secret: str, salt: str = 'qr-service-salt') -> str:
    key = derive_key(secret, salt)
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(content.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded)
    combined = iv + encrypted
    encoded = base64.b64encode(combined).decode('utf-8')
    key_hash = hashlib.sha256(key).hexdigest()[:16]
    payload = {
        'v': 1,
        'd': encoded,
        'h': key_hash
    }
    return ENCRYPT_PREFIX + base64.b64encode(json.dumps(payload).encode('utf-8')).decode('utf-8')

def decrypt_content(encrypted_str: str, secret: str, salt: str = 'qr-service-salt') -> dict:
    if not encrypted_str.startswith(ENCRYPT_PREFIX):
        return {'success': False, 'error': 'not_encrypted', 'content': encrypted_str}
    
    try:
        payload_b64 = encrypted_str[len(ENCRYPT_PREFIX):]
        payload = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
        
        key = derive_key(secret, salt)
        key_hash = hashlib.sha256(key).hexdigest()[:16]
        
        if payload.get('h') != key_hash:
            return {'success': False, 'error': 'wrong_key', 'content': None}
        
        combined = base64.b64decode(payload['d'])
        iv = combined[:16]
        ciphertext = combined[16:]
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_padded = cipher.decrypt(ciphertext)
        decrypted = unpad(decrypted_padded, AES.block_size).decode('utf-8')
        
        return {'success': True, 'error': None, 'content': decrypted}
    except Exception as e:
        return {'success': False, 'error': f'decrypt_failed: {str(e)}', 'content': None}

def is_encrypted_qr(content: str) -> bool:
    return content.startswith(ENCRYPT_PREFIX)

def get_key_hash(secret: str, salt: str = 'qr-service-salt') -> str:
    key = derive_key(secret, salt)
    return hashlib.sha256(key).hexdigest()[:16]
