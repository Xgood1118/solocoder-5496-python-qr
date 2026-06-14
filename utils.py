import hashlib
import re
import ipaddress
from datetime import datetime
from urllib.parse import urlparse

def get_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def is_url(content: str) -> bool:
    try:
        result = urlparse(content)
        return all([result.scheme, result.netloc]) and result.scheme in ('http', 'https', 'ftp', 'ftps')
    except:
        return False

def is_wifi_content(content: str) -> bool:
    return content.startswith('WIFI:') and 'T:' in content and 'S:' in content

def parse_wifi_content(content: str) -> dict:
    if not is_wifi_content(content):
        return {}
    result = {}
    pattern = r'([TSPH]):([^;]*)'
    matches = re.findall(pattern, content)
    for key, value in matches:
        if key == 'T':
            result['type'] = value
        elif key == 'S':
            result['ssid'] = value
        elif key == 'P':
            result['password'] = value
        elif key == 'H':
            result['hidden'] = value.lower() == 'true'
    return result

def generate_wifi_content(ssid: str, password: str = '', auth_type: str = 'WPA', hidden: bool = False) -> str:
    parts = [f'T:{auth_type}', f'S:{ssid}']
    if password:
        parts.append(f'P:{password}')
    if hidden:
        parts.append('H:true')
    parts.append(';')
    return 'WIFI:' + ';'.join(parts)

def generate_vcard_content(fn: str, org: str = '', title: str = '', phone: str = '', 
                           email: str = '', url: str = '', note: str = '') -> str:
    lines = ['BEGIN:VCARD', 'VERSION:3.0']
    if fn:
        lines.append(f'FN:{fn}')
    if org:
        lines.append(f'ORG:{org}')
    if title:
        lines.append(f'TITLE:{title}')
    if phone:
        lines.append(f'TEL;TYPE=CELL:{phone}')
    if email:
        lines.append(f'EMAIL:{email}')
    if url:
        lines.append(f'URL:{url}')
    if note:
        lines.append(f'NOTE:{note}')
    lines.append('END:VCARD')
    return '\n'.join(lines)

def validate_hex_color(color: str) -> bool:
    if not color:
        return False
    pattern = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
    return bool(re.match(pattern, color))

def get_client_ip(request) -> str:
    if request.headers.getlist('X-Forwarded-For'):
        ip = request.headers.getlist('X-Forwarded-For')[0].split(',')[0].strip()
    else:
        ip = request.remote_addr or 'unknown'
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return 'unknown'

def timestamp_now() -> int:
    return int(datetime.now().timestamp())

def format_timestamp(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
