import requests
import json
import base64
import io
import sys

base_url = 'http://localhost:5050'

def test_health():
    print('=== 测试1: 健康检查 ===')
    resp = requests.get(f'{base_url}/api/health')
    print(f'  Status: {resp.status_code}')
    print(f'  Body: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}')

def test_generate_png():
    print('\n=== 测试2: 生成文本二维码 PNG ===')
    resp = requests.post(f'{base_url}/api/generate', json={
        'content': 'Hello from QR Service API!',
        'format': 'png',
        'error_correction': 'M',
        'style': 'square',
        'fg_color': '#1a1a2e',
        'bg_color': '#eaeaea'
    })
    print(f'  Status: {resp.status_code}')
    print(f'  Content-Type: {resp.headers.get("Content-Type")}')
    print(f'  Size: {len(resp.content)} bytes')
    return resp.content

def test_generate_wifi():
    print('\n=== 测试3: 生成 WiFi 二维码 ===')
    resp = requests.post(f'{base_url}/api/generate', json={
        'content_type': 'wifi',
        'ssid': 'OfficeNetwork',
        'password': 'SecurePass123',
        'auth_type': 'WPA',
        'format': 'png',
        'style': 'dots'
    })
    print(f'  Status: {resp.status_code}')
    print(f'  Size: {len(resp.content)} bytes')

def test_generate_vcard():
    print('\n=== 测试4: 生成 vCard 二维码 SVG ===')
    resp = requests.post(f'{base_url}/api/generate', json={
        'content_type': 'vcard',
        'fn': '李四',
        'org': '市场部',
        'phone': '13900139000',
        'email': 'lisi@company.com',
        'format': 'svg'
    })
    print(f'  Status: {resp.status_code}')
    print(f'  Content-Type: {resp.headers.get("Content-Type")}')
    print(f'  Size: {len(resp.content)} bytes')
    svg_text = resp.text[:200]
    print(f'  SVG 前200字符: {svg_text}...')

def test_scan(png_content):
    print('\n=== 测试5: 上传图片识别二维码 ===')
    files = {'image': ('test.png', png_content, 'image/png')}
    resp = requests.post(f'{base_url}/api/scan', files=files)
    print(f'  Status: {resp.status_code}')
    result = resp.json()
    print(f'  成功: {result["success"]}')
    print(f'  数量: {result["count"]}')
    if result['results']:
        r = result['results'][0]
        print(f'  内容: {r["data"]}')
        print(f'  类型: {r["content_type"]}')
        print(f'  位置: {r["rect"]}')
        if 'frequency' in r:
            print(f'  频次信息: {r["frequency"]}')
    if 'watermark' in result:
        print(f'  水印信息: {result["watermark"]}')
    return result

def test_url_safety():
    print('\n=== 测试6: URL 安全检测 ===')
    resp = requests.post(f'{base_url}/api/url/check', json={
        'url': 'https://www.taobao.com/item?id=123&redirect=http://evil.com'
    })
    print(f'  Status: {resp.status_code}')
    result = resp.json()
    print(f'  等级: {result["level"]}')
    print(f'  风险分数: {result["risk_score"]}')
    print(f'  原因: {result["reasons"]}')

def test_equivalent():
    print('\n=== 测试7: 等效二维码判断 ===')
    resp = requests.post(f'{base_url}/api/equivalent', json={
        'contents': [
            'Same content here',
            'Same content here',
            'Different content'
        ]
    })
    print(f'  Status: {resp.status_code}')
    result = resp.json()
    print(f'  等效分组: {result["equivalent_groups"]}')
    print(f'  唯一hash数: {result["unique_hashes"]}')

def test_encrypted():
    print('\n=== 测试8: 加密二维码生成与解密 ===')
    resp = requests.post(f'{base_url}/api/generate', json={
        'content_type': 'encrypted',
        'plain_content': 'Confidential data 机密信息',
        'secret': 'my-secret-key-123',
        'format': 'png'
    })
    print(f'  加密生成 Status: {resp.status_code}, Size: {len(resp.content)} bytes')

    files = {'image': ('encrypted.png', resp.content, 'image/png')}
    scan_resp = requests.post(f'{base_url}/api/scan', files=files)
    scan_result = scan_resp.json()
    if scan_result['results']:
        encrypted_data = scan_result['results'][0]['data']
        print(f'  识别出加密数据, 长度: {len(encrypted_data)}')

        decrypt_resp = requests.post(f'{base_url}/api/scan/decrypt', json={
            'content': encrypted_data,
            'secret': 'my-secret-key-123'
        })
        decrypt_result = decrypt_resp.json()
        print(f'  正确密钥解密成功: {decrypt_result["success"]}')
        if decrypt_result['success']:
            print(f'  解密内容: {decrypt_result["content"]}')
            print(f'  解密内容类型: {decrypt_result.get("content_type")}')

        wrong_resp = requests.post(f'{base_url}/api/scan/decrypt', json={
            'content': encrypted_data,
            'secret': 'wrong-key'
        })
        wrong_result = wrong_resp.json()
        print(f'  错误密钥解密: {wrong_result["success"]}, 错误: {wrong_result["error"]}')

def test_batch():
    print('\n=== 测试9: 批量生成 ===')
    resp = requests.post(f'{base_url}/api/generate/batch', json={
        'format': 'png',
        'style': 'rounded',
        'fg_color': '#2d3436',
        'items': [
            {'content': 'Batch item 001', 'filename': 'qr_001.png'},
            {'content': 'Batch item 002', 'filename': 'qr_002.png'},
            {'content': 'Batch item 003', 'filename': 'qr_003.png'},
            {'content': 'Batch item 004', 'filename': 'qr_004.png'},
            {'content': 'Batch item 005', 'filename': 'qr_005.png'},
        ]
    })
    print(f'  Status: {resp.status_code}')
    print(f'  Content-Type: {resp.headers.get("Content-Type")}')
    print(f'  ZIP 大小: {len(resp.content)} bytes')

def test_stats():
    print('\n=== 测试10: 获取统计 ===')
    resp = requests.get(f'{base_url}/api/stats?days=7')
    print(f'  Status: {resp.status_code}')
    stats = resp.json()
    print(f'  生成统计: {stats["generation"]}')
    print(f'  扫描统计: {stats["scan"]}')
    print(f'  Top扫描: {len(stats["top_scanned"])} 条')

def test_alerts():
    print('\n=== 测试11: 获取告警 ===')
    resp = requests.get(f'{base_url}/api/alerts?limit=10')
    print(f'  Status: {resp.status_code}')
    result = resp.json()
    print(f'  告警数量: {result["count"]}')
    print(f'  告警列表: {result["alerts"][:3] if result["alerts"] else "无"}')

def test_watermark_extract(png_content):
    print('\n=== 测试12: 提取水印 ===')
    files = {'image': ('test.png', png_content, 'image/png')}
    resp = requests.post(f'{base_url}/api/watermark/extract', files=files)
    print(f'  Status: {resp.status_code}')
    result = resp.json()
    print(f'  有水印: {result.get("has_watermark")}')
    if result.get('has_watermark'):
        print(f'  水印数据: {result.get("data")}')

def test_pdf_generate():
    print('\n=== 测试13: 生成 PDF 格式 ===')
    resp = requests.post(f'{base_url}/api/generate', json={
        'content': 'PDF QR Code Test',
        'format': 'pdf'
    })
    print(f'  Status: {resp.status_code}')
    print(f'  Content-Type: {resp.headers.get("Content-Type")}')
    print(f'  Size: {len(resp.content)} bytes')

def test_gradient_style():
    print('\n=== 测试14: 渐变+透明背景样式 ===')
    resp = requests.post(f'{base_url}/api/generate', json={
        'content': 'Gradient Style Test',
        'format': 'png',
        'style': 'dots',
        'gradient_start': '#FF6B6B',
        'gradient_end': '#4ECDC4',
        'gradient_direction': 'diagonal',
        'bg_color': '#FFFFFF'
    })
    print(f'  Status: {resp.status_code}')
    print(f'  Size: {len(resp.content)} bytes')

if __name__ == '__main__':
    try:
        test_health()
        png = test_generate_png()
        test_generate_wifi()
        test_generate_vcard()
        test_scan(png)
        test_url_safety()
        test_equivalent()
        test_encrypted()
        test_batch()
        test_stats()
        test_alerts()
        test_watermark_extract(png)
        test_pdf_generate()
        test_gradient_style()
        print('\n' + '='*50)
        print('All API tests passed!')
        print('='*50)
    except Exception as e:
        print(f'\nTest failed: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
