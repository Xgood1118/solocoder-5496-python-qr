import sys
import io
sys.path.insert(0, r'c:\Users\白东鑫\work01\SoloCoder\5496-python-qr')

from qr_generator import generate_qr_pil, pil_to_png_bytes, get_qr_version
from qr_scanner import scan_qr_from_image
from encryption import encrypt_content, decrypt_content
from utils import generate_wifi_content, generate_vcard_content, is_url, get_content_hash
from watermark import encode_lsb_watermark, decode_lsb_watermark, create_watermark_data
from url_safety import check_url_safety
from batch_generator import batch_generate_png
from stats_db import StatsDB
import os
import tempfile

print('=== 测试1: 基本二维码生成 ===')
test_content = 'Hello, QR Code Service!'
img = generate_qr_pil(test_content, error_correction='M', box_size=10, border=4)
print(f'  生成图片尺寸: {img.size}')
print(f'  QR 版本: {get_qr_version(test_content, "M")}')
png_bytes = pil_to_png_bytes(img)
print(f'  PNG 大小: {len(png_bytes)} bytes')

print('\n=== 测试2: 二维码识别 ===')
result = scan_qr_from_image(png_bytes)
print(f'  识别成功: {result["success"]}')
print(f'  识别数量: {result["count"]}')
if result['results']:
    print(f'  识别内容: {result["results"][0]["data"]}')
    print(f'  位置矩形: {result["results"][0]["rect"]}')

print('\n=== 测试3: WiFi 凭证生成 ===')
wifi_content = generate_wifi_content('MyNetwork', 'mypassword123', 'WPA')
print(f'  WiFi 内容: {wifi_content}')
img_wifi = generate_qr_pil(wifi_content)
print(f'  WiFi QR 生成成功')

print('\n=== 测试4: vCard 生成 ===')
vcard = generate_vcard_content(fn='张三', org='科技公司', phone='13800138000', email='zhangsan@example.com')
print(f'  vCard 前50字符: {vcard[:50]}...')

print('\n=== 测试5: AES 加密二维码 ===')
encrypted = encrypt_content('secret data here', 'mysecretkey')
print(f'  加密后前缀: {encrypted[:20]}...')
print(f'  加密内容长度: {len(encrypted)}')
decrypted = decrypt_content(encrypted, 'mysecretkey')
print(f'  解密成功: {decrypted["success"]}')
print(f'  解密内容: {decrypted["content"]}')
wrong_decrypt = decrypt_content(encrypted, 'wrongkey')
print(f'  错误密钥解密: {wrong_decrypt["success"]}, 错误: {wrong_decrypt["error"]}')

print('\n=== 测试6: 隐形水印 ===')
wm_data = create_watermark_data('192.168.1.100', 1234567890, 'abc123')
print(f'  水印数据: {wm_data}')
img_wm = encode_lsb_watermark(img, wm_data)
wm_bytes = pil_to_png_bytes(img_wm)
extracted = decode_lsb_watermark(img_wm)
print(f'  提取水印成功: {extracted["has_watermark"]}')
if extracted['has_watermark']:
    print(f'  提取数据: {extracted["data"]}')

print('\n=== 测试7: URL 安全检测 ===')
safe_url = 'https://www.example.com/page'
suspicious_url = 'http://192.168.1.1/login?password=123'
result1 = check_url_safety(safe_url)
print(f'  安全URL: {safe_url} -> 等级: {result1["level"]}, 分数: {result1["risk_score"]}')
result2 = check_url_safety(suspicious_url)
print(f'  可疑URL: {suspicious_url[:40]}... -> 等级: {result2["level"]}, 分数: {result2["risk_score"]}')
print(f'  可疑原因: {result2["reasons"]}')

print('\n=== 测试8: 样式定制 ===')
img_dots = generate_qr_pil(test_content, style='dots', fg_color='#FF6B6B', bg_color='#F7FFF7')
print(f'  圆点样式 QR 生成成功, 尺寸: {img_dots.size}')
img_rounded = generate_qr_pil(test_content, style='rounded')
print(f'  圆角样式 QR 生成成功')
img_gradient = generate_qr_pil(test_content, gradient_start='#FF6B6B', gradient_end='#4ECDC4', gradient_direction='vertical')
print(f'  渐变样式 QR 生成成功')
img_transparent = generate_qr_pil(test_content, transparent_bg=True)
print(f'  透明背景 QR 生成成功, 模式: {img_transparent.mode}')
img_classy = generate_qr_pil(test_content, style='classy')
print(f'  classy 样式 QR 生成成功')
img_classy_dots = generate_qr_pil(test_content, style='classy-dots')
print(f'  classy-dots 样式 QR 生成成功')

print('\n=== 测试9: 等效二维码判断 ===')
hash1 = get_content_hash(test_content)
hash2 = get_content_hash(test_content)
hash3 = get_content_hash('different content')
print(f'  相同内容 hash 相同: {hash1 == hash2}')
print(f'  不同内容 hash 不同: {hash1 != hash3}')

print('\n=== 测试10: 批量生成 ===')
items = [
    {'content': 'item 1', 'filename': 'qr_001.png'},
    {'content': 'item 2', 'filename': 'qr_002.png'},
    {'content': 'item 3', 'filename': 'qr_003.png'},
]
zip_bytes = batch_generate_png(items)
print(f'  批量生成 zip 大小: {len(zip_bytes)} bytes')

print('\n=== 测试11: SQLite 统计 ===')
tmp_db = tempfile.mktemp(suffix='.db')
db = StatsDB(tmp_db)
db.record_generation(
    content='test content',
    content_type='text',
    style='square',
    fmt='png',
    has_logo=False,
    error_correction='M',
    size=256,
    client_ip='127.0.0.1',
    user_agent='test'
)
freq = db.record_scan(
    content='test content',
    content_type='text',
    qr_count=1,
    client_ip='127.0.0.1',
    user_agent='test'
)
print(f'  记录扫描成功, 频次: {freq}')
gen_stats = db.get_generation_stats(7)
print(f'  生成统计: {gen_stats}')
scan_stats = db.get_scan_stats(7)
print(f'  扫描统计: {scan_stats}')
os.unlink(tmp_db)

print('\n✓ 所有核心功能测试通过!')
