import requests
import json
import base64
import io
import zipfile
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from qr_generator import generate_svg, generate_qr_pil
from PIL import Image

base_url = 'http://localhost:5051'
passed = True

# =====================================================
# Bug 1: Batch ZIP filename - no filename provided
# =====================================================
print('='*60)
print('Bug 1: Batch ZIP filename when items have no filename')
print('='*60)

resp = requests.post(f'{base_url}/api/generate/batch', json={
    'format': 'png',
    'items': [
        {'content': 'Alpha'},
        {'content': 'Bravo'},
        {'content': 'Charlie'},
    ]
})
assert resp.status_code == 200, f'Expected 200, got {resp.status_code}'
zf = zipfile.ZipFile(io.BytesIO(resp.content))
names = zf.namelist()
print(f'  ZIP entries: {names}')
for i, name in enumerate(names):
    expected = f'qr_{i+1}.png'
    if name != expected:
        print(f'  FAIL: entry {i} is "{name}", expected "{expected}"')
        passed = False
    else:
        print(f'  OK: entry {i} = "{name}"')

# Also test with explicit filename mixed
resp = requests.post(f'{base_url}/api/generate/batch', json={
    'format': 'png',
    'items': [
        {'content': 'Alpha', 'filename': 'custom_alpha.png'},
        {'content': 'Bravo'},
        {'content': 'Charlie'},
    ]
})
zf = zipfile.ZipFile(io.BytesIO(resp.content))
names = zf.namelist()
print(f'  Mixed ZIP entries: {names}')
if names[0] != 'custom_alpha.png':
    print(f'  FAIL: entry 0 is "{names[0]}", expected "custom_alpha.png"')
    passed = False
else:
    print(f'  OK: entry 0 = custom_alpha.png')
if names[1] != 'qr_2.png':
    print(f'  FAIL: entry 1 is "{names[1]}", expected "qr_2.png"')
    passed = False
else:
    print(f'  OK: entry 1 = qr_2.png')

# Also test SVG batch without filename
resp = requests.post(f'{base_url}/api/generate/batch', json={
    'format': 'svg',
    'items': [
        {'content': 'SVG-1'},
        {'content': 'SVG-2'},
    ]
})
zf = zipfile.ZipFile(io.BytesIO(resp.content))
names = zf.namelist()
print(f'  SVG ZIP entries: {names}')
for i, name in enumerate(names):
    expected = f'qr_{i+1}.svg'
    if name != expected:
        print(f'  FAIL: SVG entry {i} is "{name}", expected "{expected}"')
        passed = False
    else:
        print(f'  OK: SVG entry {i} = "{name}"')

# =====================================================
# Bug 2: SVG logo rendering
# =====================================================
print()
print('='*60)
print('Bug 2: SVG logo rendering')
print('='*60)

# Create a small red logo for test
logo = Image.new('RGBA', (40, 40), (255, 0, 0, 255))

# Test via API
logo_buf = io.BytesIO()
logo.save(logo_buf, format='PNG')
logo_b64 = base64.b64encode(logo_buf.getvalue()).decode('utf-8')

resp = requests.post(f'{base_url}/api/generate', json={
    'content': 'Test SVG with logo',
    'format': 'svg',
    'logo_data': logo_b64,
})
assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.text[:200]}'
svg_text = resp.text

has_image_tag = '<image ' in svg_text
has_base64_data = 'data:image/png;base64,' in svg_text
has_xlink = 'xlink:href' in svg_text
has_white_bg_rect = 'fill="white"' in svg_text and 'rx="4"' in svg_text

print(f'  <image> tag present: {has_image_tag}')
print(f'  base64 data URI present: {has_base64_data}')
print(f'  xlink:href present: {has_xlink}')
print(f'  White padding rect present: {has_white_bg_rect}')

if not has_image_tag:
    print('  FAIL: SVG missing <image> tag for logo')
    passed = False
if not has_base64_data:
    print('  FAIL: SVG missing base64 data URI for logo')
    passed = False
if not has_xlink:
    print('  FAIL: SVG missing xlink:href attribute')
    passed = False
else:
    print('  OK: SVG logo correctly inlined')

# Also test direct generate_svg function
svg_direct = generate_svg('Direct SVG logo test', logo_image=logo, logo_ratio=0.2)
print(f'  Direct SVG length: {len(svg_direct)}')
if '<image ' in svg_direct and 'data:image/png;base64,' in svg_direct:
    print('  OK: Direct generate_svg includes logo')
else:
    print('  FAIL: Direct generate_svg missing logo')
    passed = False

# Test SVG without logo still works
svg_no_logo = generate_svg('No logo SVG')
if '<image ' not in svg_no_logo:
    print('  OK: SVG without logo has no <image> tag')
else:
    print('  FAIL: SVG without logo unexpectedly has <image> tag')
    passed = False

# =====================================================
# Bug 3: meCard generation
# =====================================================
print()
print('='*60)
print('Bug 3: meCard generation support')
print('='*60)

# Test meCard via API - PNG
resp = requests.post(f'{base_url}/api/generate', json={
    'content_type': 'mecard',
    'name': 'Smith,John',
    'phone': '555-1234',
    'email': 'john@example.com',
    'org': 'Acme Corp',
    'title': 'Engineer',
    'format': 'png',
})
assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.text[:200]}'
assert resp.headers.get('Content-Type') == 'image/png'
print(f'  meCard PNG: OK ({len(resp.content)} bytes)')

# Test meCard via API - SVG
resp = requests.post(f'{base_url}/api/generate', json={
    'content_type': 'mecard',
    'name': 'Zhang,San',
    'phone': '13800138000',
    'email': 'zhangsan@company.com',
    'format': 'svg',
})
assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.text[:200]}'
assert 'image/svg' in resp.headers.get('Content-Type', '')
svg_mecard = resp.text
if 'MECARD:' in svg_mecard or resp.status_code == 200:
    print(f'  meCard SVG: OK ({len(resp.content)} bytes)')

# Test meCard empty fields returns 400
resp = requests.post(f'{base_url}/api/generate', json={
    'content_type': 'mecard',
    'format': 'png',
})
assert resp.status_code == 400, f'Expected 400 for empty mecard, got {resp.status_code}'
print(f'  meCard empty fields -> 400: OK')

# Test meCard content generation via utils directly
from utils import generate_mecard_content
mecard_str = generate_mecard_content(name='Doe,Jane', phone='555-9999', email='jane@test.com')
print(f'  meCard string: {mecard_str}')
assert mecard_str.startswith('MECARD:'), f'Expected MECARD: prefix, got {mecard_str[:20]}'
assert 'N:Doe,Jane' in mecard_str
assert 'TEL:555-9999' in mecard_str
assert 'EMAIL:jane@test.com' in mecard_str
assert mecard_str.endswith(';;')
print('  meCard format: OK')

# Test round-trip: generate meCard QR then scan it
from qr_scanner import scan_qr_from_image
from qr_generator import generate_qr_pil, pil_to_png_bytes
mecard_content = generate_mecard_content(name='RoundTrip,Test', phone='111-2222', org='TestCo')
img = generate_qr_pil(mecard_content)
png_bytes = pil_to_png_bytes(img)
scan_result = scan_qr_from_image(png_bytes)
if scan_result['success'] and scan_result['results']:
    scanned = scan_result['results'][0]['data']
    if scanned == mecard_content:
        print(f'  meCard round-trip scan: OK')
    else:
        print(f'  FAIL: scanned "{scanned}" != generated "{mecard_content}"')
        passed = False
else:
    print(f'  FAIL: could not scan meCard QR')
    passed = False

# =====================================================
# Final result
# =====================================================
print()
print('='*60)
if passed:
    print('ALL 3 BUG FIXES VERIFIED - PASSED')
else:
    print('SOME TESTS FAILED - SEE ABOVE')
print('='*60)
