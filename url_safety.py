import re
import hashlib
from urllib.parse import urlparse, unquote
from typing import Tuple

SAFE = 'safe'
SUSPICIOUS = 'suspicious'
DANGEROUS = 'dangerous'

SUSPICIOUS_KEYWORDS = [
    'login', 'signin', 'verify', 'confirm', 'update', 'secure',
    'account', 'password', 'credit', 'bank', 'paypal', 'wallet',
    'bitcoin', 'crypto', 'gift', 'free', 'win', 'winner',
    'lucky', 'claim', 'reward', 'prize',
]

DANGEROUS_KEYWORDS = [
    'malware', 'virus', 'trojan', 'ransomware', 'phish',
    'scam', 'fraud', 'hack', 'exploit',
]

DANGEROUS_TLDS = ['.tk', '.ml', '.ga', '.cf', '.gq']

SUSPICIOUS_PATTERNS = [
    r'ip-address',
    r'(\d{1,3}\.){3}\d{1,3}',
]

def check_url_safety(url: str) -> dict:
    if not url:
        return {'level': SAFE, 'reasons': [], 'risk_score': 0}
    
    try:
        parsed = urlparse(url)
    except:
        return {'level': SUSPICIOUS, 'reasons': ['invalid_url_format'], 'risk_score': 30}
    
    reasons = []
    risk_score = 0
    
    scheme = parsed.scheme.lower()
    if scheme not in ('http', 'https', 'ftp', 'ftps'):
        reasons.append('unknown_scheme')
        risk_score += 20
    elif scheme == 'http':
        reasons.append('not_https')
        risk_score += 10
    
    netloc = parsed.netloc.lower()
    
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', netloc.split(':')[0]):
        reasons.append('ip_address_domain')
        risk_score += 15
    
    for tld in DANGEROUS_TLDS:
        if netloc.endswith(tld):
            reasons.append(f'suspicious_tld_{tld}')
            risk_score += 25
            break
    
    if '@' in netloc:
        reasons.append('contains_username')
        risk_score += 30
    
    if netloc.count('.') > 3:
        reasons.append('too_many_subdomains')
        risk_score += 10
    
    url_lower = url.lower()
    unquoted = unquote(url_lower)
    
    for kw in DANGEROUS_KEYWORDS:
        if kw in unquoted:
            reasons.append(f'dangerous_keyword_{kw}')
            risk_score += 40
    
    for kw in SUSPICIOUS_KEYWORDS:
        if kw in unquoted:
            reasons.append(f'suspicious_keyword_{kw}')
            risk_score += 15
    
    if len(url) > 200:
        reasons.append('url_too_long')
        risk_score += 10
    
    if parsed.query:
        params = parsed.query.split('&')
        if len(params) > 10:
            reasons.append('too_many_params')
            risk_score += 10
        
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                if key.lower() in ('redirect', 'url', 'next', 'go', 'to'):
                    if value.startswith('http') or value.startswith('//'):
                        reasons.append('redirect_param')
                        risk_score += 25
    
    if re.search(r'(.)\1{10,}', url_lower):
        reasons.append('suspicious_repetition')
        risk_score += 15
    
    if risk_score >= 60:
        level = DANGEROUS
    elif risk_score >= 25:
        level = SUSPICIOUS
    else:
        level = SAFE
    
    return {
        'level': level,
        'risk_score': risk_score,
        'reasons': reasons,
        'domain': netloc,
        'scheme': scheme,
    }

def get_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()
