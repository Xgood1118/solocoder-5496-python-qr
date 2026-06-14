import io
import json
import hashlib
from PIL import Image
import numpy as np

WATERMARK_MAGIC = b'QRWM'

def encode_lsb_watermark(img: Image.Image, data: dict) -> Image.Image:
    json_data = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    
    payload = WATERMARK_MAGIC + len(json_data).to_bytes(4, 'big') + json_data
    
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA')
    
    pixels = np.array(img)
    original_shape = pixels.shape
    
    flat = pixels.flatten()
    
    bits_needed = len(payload) * 8
    if bits_needed > len(flat):
        raise ValueError('Image too small to embed watermark')
    
    flat = flat.astype(np.uint8)
    
    bit_index = 0
    for byte in payload:
        for bit in range(7, -1, -1):
            if bit_index >= len(flat):
                break
            pixel_val = int(flat[bit_index])
            if (byte >> bit) & 1:
                pixel_val = pixel_val | 1
            else:
                pixel_val = pixel_val & 0xFE
            flat[bit_index] = pixel_val
            bit_index += 1
    
    new_pixels = flat.reshape(original_shape)
    
    return Image.fromarray(new_pixels.astype('uint8'), mode=img.mode)

def decode_lsb_watermark(img: Image.Image) -> dict:
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA')
    
    pixels = np.array(img).flatten()
    
    bits = []
    for i in range(min(len(pixels), 64 * 8)):
        bits.append(pixels[i] & 1)
    
    magic_bytes = _bits_to_bytes(bits[:len(WATERMARK_MAGIC) * 8])
    if magic_bytes != WATERMARK_MAGIC:
        return {'has_watermark': False, 'data': None}
    
    len_bits_start = len(WATERMARK_MAGIC) * 8
    len_bits_end = len_bits_start + 32
    length = int.from_bytes(_bits_to_bytes(bits[len_bits_start:len_bits_end]), 'big')
    
    total_bits = len_bits_end + length * 8
    if total_bits > len(pixels):
        return {'has_watermark': False, 'data': None, 'error': 'incomplete_watermark'}
    
    all_bits = []
    for i in range(total_bits):
        all_bits.append(pixels[i] & 1)
    
    data_bytes = _bits_to_bytes(all_bits[len_bits_end:total_bits])
    
    try:
        data = json.loads(data_bytes.decode('utf-8'))
        return {'has_watermark': True, 'data': data}
    except:
        return {'has_watermark': False, 'data': None, 'error': 'decode_failed'}

def _bits_to_bytes(bits: list) -> bytes:
    result = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(min(8, len(bits) - i)):
            byte = (byte << 1) | bits[i + j]
        result.append(byte)
    return bytes(result)

def create_watermark_data(client_ip: str, timestamp: int, content_hash: str = '',
                          generator: str = 'qr-service', extra: dict = None) -> dict:
    data = {
        'ip': client_ip,
        'ts': timestamp,
        'gen': generator,
        'ch': content_hash[:16] if content_hash else '',
    }
    if extra:
        data.update(extra)
    return data

def embed_watermark_to_png(png_bytes: bytes, watermark_data: dict) -> bytes:
    img = Image.open(io.BytesIO(png_bytes))
    watermarked = encode_lsb_watermark(img, watermark_data)
    
    buf = io.BytesIO()
    watermarked.save(buf, format='PNG')
    return buf.getvalue()

def extract_watermark_from_png(png_bytes: bytes) -> dict:
    img = Image.open(io.BytesIO(png_bytes))
    return decode_lsb_watermark(img)
