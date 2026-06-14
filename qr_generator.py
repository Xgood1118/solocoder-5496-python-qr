import io
import base64
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

ERROR_LEVEL_MAP = {
    'L': ERROR_CORRECT_L,
    'M': ERROR_CORRECT_M,
    'Q': ERROR_CORRECT_Q,
    'H': ERROR_CORRECT_H,
}

STYLE_SQUARE = 'square'
STYLE_ROUNDED = 'rounded'
STYLE_DOTS = 'dots'
STYLE_CLASSY = 'classy'
STYLE_CLASSY_DOTS = 'classy-dots'

def _get_error_level(level: str, has_logo: bool = False) -> int:
    if has_logo:
        return ERROR_CORRECT_H
    return ERROR_LEVEL_MAP.get(level.upper(), ERROR_CORRECT_M)

def generate_qr_pil(content: str, error_correction: str = 'M', box_size: int = 10,
                    border: int = 4, style: str = STYLE_SQUARE,
                    fg_color: str = '#000000', bg_color: str = '#FFFFFF',
                    transparent_bg: bool = False, gradient_start: str = None,
                    gradient_end: str = None, gradient_direction: str = 'vertical',
                    logo_image: Image.Image = None, logo_ratio: float = 0.2,
                    watermark_text: str = None) -> Image.Image:
    
    has_logo = logo_image is not None
    error_level = _get_error_level(error_correction, has_logo)
    
    qr = qrcode.QRCode(
        version=None,
        error_correction=error_level,
        box_size=box_size,
        border=border,
    )
    qr.add_data(content)
    qr.make(fit=True)
    
    matrix = qr.get_matrix()
    size = len(matrix)
    img_size = size * box_size
    
    if transparent_bg:
        img = Image.new('RGBA', (img_size, img_size), (255, 255, 255, 0))
    else:
        bg_rgb = _hex_to_rgb(bg_color)
        img = Image.new('RGB', (img_size, img_size), bg_rgb)
        if gradient_start and gradient_end:
            img = _apply_gradient_background(img, gradient_start, gradient_end, gradient_direction, bg_rgb)
    
    fg_rgb = _hex_to_rgb(fg_color) if not transparent_bg else _hex_to_rgb(fg_color) + (255,)
    mode = 'RGBA' if transparent_bg else 'RGB'
    
    if style == STYLE_SQUARE:
        img = _draw_squares(img, matrix, box_size, fg_rgb, mode)
    elif style == STYLE_ROUNDED:
        img = _draw_rounded(img, matrix, box_size, fg_rgb, mode, radius_ratio=0.3)
    elif style == STYLE_DOTS:
        img = _draw_dots(img, matrix, box_size, fg_rgb, mode)
    elif style == STYLE_CLASSY:
        img = _draw_classy(img, matrix, box_size, fg_rgb, mode)
    elif style == STYLE_CLASSY_DOTS:
        img = _draw_classy_dots(img, matrix, box_size, fg_rgb, mode)
    else:
        img = _draw_squares(img, matrix, box_size, fg_rgb, mode)
    
    if gradient_start and gradient_end and style != STYLE_SQUARE:
        img = _apply_gradient_fg(img, matrix, box_size, gradient_start, gradient_end, gradient_direction, mode)
    
    if has_logo:
        img = _add_logo(img, logo_image, logo_ratio)
    
    if watermark_text:
        img = _add_visible_watermark(img, watermark_text)
    
    return img

def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def _apply_gradient_background(img: Image.Image, start_color: str, end_color: str, 
                               direction: str, default_bg: tuple) -> Image.Image:
    w, h = img.size
    start_rgb = _hex_to_rgb(start_color)
    end_rgb = _hex_to_rgb(end_color)
    
    gradient = Image.new('RGB', (w, h))
    pixels = gradient.load()
    
    if direction == 'horizontal':
        for x in range(w):
            ratio = x / (w - 1) if w > 1 else 0
            r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
            g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
            b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
            for y in range(h):
                pixels[x, y] = (r, g, b)
    elif direction == 'diagonal':
        max_dist = (w - 1) + (h - 1)
        for x in range(w):
            for y in range(h):
                ratio = (x + y) / max_dist if max_dist > 0 else 0
                r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
                g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
                b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
                pixels[x, y] = (r, g, b)
    else:
        for y in range(h):
            ratio = y / (h - 1) if h > 1 else 0
            r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
            g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
            b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
            for x in range(w):
                pixels[x, y] = (r, g, b)
    
    return gradient

def _apply_gradient_fg(img: Image.Image, matrix: list, box_size: int,
                       start_color: str, end_color: str, direction: str, mode: str) -> Image.Image:
    w, h = img.size
    start_rgb = _hex_to_rgb(start_color)
    end_rgb = _hex_to_rgb(end_color)
    
    pixels = img.load()
    
    if mode == 'RGBA':
        for x in range(w):
            for y in range(h):
                if pixels[x, y][3] > 0:
                    if direction == 'horizontal':
                        ratio = x / (w - 1) if w > 1 else 0
                    elif direction == 'diagonal':
                        ratio = (x + y) / ((w - 1) + (h - 1)) if w + h > 2 else 0
                    else:
                        ratio = y / (h - 1) if h > 1 else 0
                    r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
                    g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
                    b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
                    pixels[x, y] = (r, g, b, pixels[x, y][3])
    else:
        bg_pixels = set()
        for row_idx, row in enumerate(matrix):
            for col_idx, cell in enumerate(row):
                if not cell:
                    for dy in range(box_size):
                        for dx in range(box_size):
                            px = col_idx * box_size + dx
                            py = row_idx * box_size + dy
                            bg_pixels.add((px, py))
        
        for x in range(w):
            for y in range(h):
                if (x, y) not in bg_pixels:
                    if direction == 'horizontal':
                        ratio = x / (w - 1) if w > 1 else 0
                    elif direction == 'diagonal':
                        ratio = (x + y) / ((w - 1) + (h - 1)) if w + h > 2 else 0
                    else:
                        ratio = y / (h - 1) if h > 1 else 0
                    r = int(start_rgb[0] * (1 - ratio) + end_rgb[0] * ratio)
                    g = int(start_rgb[1] * (1 - ratio) + end_rgb[1] * ratio)
                    b = int(start_rgb[2] * (1 - ratio) + end_rgb[2] * ratio)
                    pixels[x, y] = (r, g, b)
    
    return img

def _draw_squares(img: Image.Image, matrix: list, box_size: int, fg_color: tuple, mode: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    for row_idx, row in enumerate(matrix):
        for col_idx, cell in enumerate(row):
            if cell:
                x0 = col_idx * box_size
                y0 = row_idx * box_size
                x1 = x0 + box_size - 1
                y1 = y0 + box_size - 1
                draw.rectangle([x0, y0, x1, y1], fill=fg_color)
    return img

def _draw_rounded(img: Image.Image, matrix: list, box_size: int, fg_color: tuple, 
                  mode: str, radius_ratio: float = 0.3) -> Image.Image:
    draw = ImageDraw.Draw(img)
    radius = int(box_size * radius_ratio)
    if radius < 1:
        radius = 1
    
    for row_idx, row in enumerate(matrix):
        for col_idx, cell in enumerate(row):
            if cell:
                x0 = col_idx * box_size
                y0 = row_idx * box_size
                x1 = x0 + box_size - 1
                y1 = y0 + box_size - 1
                draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fg_color)
    return img

def _draw_dots(img: Image.Image, matrix: list, box_size: int, fg_color: tuple, mode: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    radius = box_size // 2 - 1
    if radius < 1:
        radius = 1
    
    for row_idx, row in enumerate(matrix):
        for col_idx, cell in enumerate(row):
            if cell:
                cx = col_idx * box_size + box_size // 2
                cy = row_idx * box_size + box_size // 2
                draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=fg_color)
    return img

def _draw_classy(img: Image.Image, matrix: list, box_size: int, fg_color: tuple, mode: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    corner_radius = box_size // 3
    if corner_radius < 1:
        corner_radius = 1
    
    for row_idx, row in enumerate(matrix):
        for col_idx, cell in enumerate(row):
            if cell:
                x0 = col_idx * box_size
                y0 = row_idx * box_size
                x1 = x0 + box_size - 1
                y1 = y0 + box_size - 1
                
                has_right = col_idx + 1 < len(row) and row[col_idx + 1]
                has_bottom = row_idx + 1 < len(matrix) and matrix[row_idx + 1][col_idx]
                has_left = col_idx > 0 and row[col_idx - 1]
                has_top = row_idx > 0 and matrix[row_idx - 1][col_idx]
                
                draw.rounded_rectangle([x0, y0, x1, y1], radius=corner_radius, fill=fg_color)
                
                if has_right and has_bottom:
                    fill_x0 = x0 + box_size // 2
                    fill_y0 = y0 + box_size // 2
                    fill_x1 = x1 + box_size // 2
                    fill_y1 = y1 + box_size // 2
                    if fill_x1 < img.width and fill_y1 < img.height:
                        draw.rectangle([fill_x0, fill_y0, fill_x1 - 1, fill_y1 - 1], fill=fg_color)
    return img

def _draw_classy_dots(img: Image.Image, matrix: list, box_size: int, fg_color: tuple, mode: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    
    for row_idx, row in enumerate(matrix):
        for col_idx, cell in enumerate(row):
            if cell:
                cx = col_idx * box_size + box_size // 2
                cy = row_idx * box_size + box_size // 2
                
                has_right = col_idx + 1 < len(row) and row[col_idx + 1]
                has_bottom = row_idx + 1 < len(matrix) and matrix[row_idx + 1][col_idx]
                
                radius = box_size // 2 - 1
                if radius < 1:
                    radius = 1
                
                draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=fg_color)
                
                if has_right:
                    rect_x0 = cx
                    rect_y0 = cy - radius
                    rect_x1 = cx + box_size
                    rect_y1 = cy + radius
                    draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=fg_color)
                
                if has_bottom:
                    rect_x0 = cx - radius
                    rect_y0 = cy
                    rect_x1 = cx + radius
                    rect_y1 = cy + box_size
                    draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill=fg_color)
    
    return img

def _add_logo(img: Image.Image, logo: Image.Image, logo_ratio: float = 0.2) -> Image.Image:
    img_w, img_h = img.size
    
    max_logo_area = img_w * img_h * logo_ratio
    
    logo_w, logo_h = logo.size
    
    if logo.mode != 'RGBA':
        logo = logo.convert('RGBA')
    
    scale = min(1.0, (max_logo_area / (logo_w * logo_h)) ** 0.5)
    new_logo_w = int(logo_w * scale)
    new_logo_h = int(logo_h * scale)
    logo = logo.resize((new_logo_w, new_logo_h), Image.LANCZOS)
    
    pos_x = (img_w - new_logo_w) // 2
    pos_y = (img_h - new_logo_h) // 2
    
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    img.paste(logo, (pos_x, pos_y), logo)
    
    return img

def _add_visible_watermark(img: Image.Image, text: str) -> Image.Image:
    from PIL import ImageFont
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype('arial.ttf', 12)
    except:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    img_w, img_h = img.size
    pos_x = img_w - text_w - 5
    pos_y = img_h - text_h - 5
    
    draw.text((pos_x, pos_y), text, fill=(128, 128, 128, 180) if img.mode == 'RGBA' else (128, 128, 128), font=font)
    
    return img

def _logo_to_svg_inline(logo: Image.Image, img_size: int, logo_ratio: float = 0.2) -> str:
    if logo.mode != 'RGBA':
        logo = logo.convert('RGBA')
    
    logo_w, logo_h = logo.size
    max_logo_area = img_size * img_size * logo_ratio
    scale = min(1.0, (max_logo_area / (logo_w * logo_h)) ** 0.5)
    new_logo_w = int(logo_w * scale)
    new_logo_h = int(logo_h * scale)
    
    logo_resized = logo.resize((new_logo_w, new_logo_h), Image.LANCZOS)
    
    buf = io.BytesIO()
    logo_resized.save(buf, format='PNG')
    logo_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    pos_x = (img_size - new_logo_w) // 2
    pos_y = (img_size - new_logo_h) // 2
    
    pad = 4
    bg_x = pos_x - pad
    bg_y = pos_y - pad
    bg_w = new_logo_w + 2 * pad
    bg_h = new_logo_h + 2 * pad
    
    parts = [
        f'<rect x="{bg_x}" y="{bg_y}" width="{bg_w}" height="{bg_h}" fill="white" rx="4"/>',
        f'<image x="{pos_x}" y="{pos_y}" width="{new_logo_w}" height="{new_logo_h}" xlink:href="data:image/png;base64,{logo_b64}"/>',
    ]
    return '\n'.join(parts)

def pil_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

def generate_svg(content: str, error_correction: str = 'M', box_size: int = 10,
                 border: int = 4, fg_color: str = '#000000', bg_color: str = '#FFFFFF',
                 transparent_bg: bool = False, logo_image: Image.Image = None,
                 logo_ratio: float = 0.2) -> str:
    
    has_logo = logo_image is not None
    error_level = _get_error_level(error_correction, has_logo)
    
    qr = qrcode.QRCode(
        version=None,
        error_correction=error_level,
        box_size=box_size,
        border=border,
    )
    qr.add_data(content)
    qr.make(fit=True)
    
    matrix = qr.get_matrix()
    size = len(matrix)
    img_size = size * box_size
    
    svg_parts = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {img_size} {img_size}" width="{img_size}" height="{img_size}">',
    ]
    
    if not transparent_bg:
        svg_parts.append(f'<rect width="{img_size}" height="{img_size}" fill="{bg_color}"/>')
    
    svg_parts.append(f'<g fill="{fg_color}">')
    
    for row_idx, row in enumerate(matrix):
        for col_idx, cell in enumerate(row):
            if cell:
                x = col_idx * box_size
                y = row_idx * box_size
                svg_parts.append(f'<rect x="{x}" y="{y}" width="{box_size}" height="{box_size}"/>')
    
    svg_parts.append('</g>')
    
    if has_logo:
        logo_svg = _logo_to_svg_inline(logo_image, img_size, logo_ratio)
        svg_parts.append(logo_svg)
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)

def generate_pdf(content: str, error_correction: str = 'M', box_size: int = 10,
                 border: int = 4, fg_color: str = '#000000', bg_color: str = '#FFFFFF',
                 logo_image: Image.Image = None) -> bytes:
    
    qr_img = generate_qr_pil(
        content=content,
        error_correction=error_correction,
        box_size=box_size,
        border=border,
        fg_color=fg_color,
        bg_color=bg_color,
        logo_image=logo_image,
    )
    
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    
    page_w, page_h = A4
    qr_size_mm = 100
    qr_size_px = qr_size_mm * 2.83465
    
    x = (page_w - qr_size_px) / 2
    y = (page_h - qr_size_px) / 2
    
    img_reader = ImageReader(qr_img)
    c.drawImage(img_reader, x, y, width=qr_size_px, height=qr_size_px)
    
    c.showPage()
    c.save()
    
    return buf.getvalue()

def get_qr_version(content: str, error_correction: str = 'M') -> int:
    error_level = ERROR_LEVEL_MAP.get(error_correction.upper(), ERROR_CORRECT_M)
    qr = qrcode.QRCode(
        version=None,
        error_correction=error_level,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    return qr.version
