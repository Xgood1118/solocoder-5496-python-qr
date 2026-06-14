import io
import zipfile
from typing import List, Dict, Any
from PIL import Image

from qr_generator import generate_qr_pil, pil_to_png_bytes, generate_svg
from watermark import encode_lsb_watermark, create_watermark_data

def batch_generate_png(items: List[Dict[str, Any]], default_options: Dict = None) -> bytes:
    zip_buf = io.BytesIO()
    
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for idx, item in enumerate(items):
            content = item.get('content', '')
            if not content:
                continue
            
            options = dict(default_options or {})
            options.update(item.get('options', {}))
            
            filename = item.get('filename', f'qr_{idx + 1}.png')
            if not filename.endswith('.png'):
                filename += '.png'
            
            img = generate_qr_pil(
                content=content,
                error_correction=options.get('error_correction', 'M'),
                box_size=options.get('box_size', 10),
                border=options.get('border', 4),
                style=options.get('style', 'square'),
                fg_color=options.get('fg_color', '#000000'),
                bg_color=options.get('bg_color', '#FFFFFF'),
                transparent_bg=options.get('transparent_bg', False),
                gradient_start=options.get('gradient_start'),
                gradient_end=options.get('gradient_end'),
                gradient_direction=options.get('gradient_direction', 'vertical'),
                logo_image=options.get('logo_image'),
                logo_ratio=options.get('logo_ratio', 0.2),
                watermark_text=options.get('watermark_text'),
            )
            
            watermark_data = options.get('watermark_data')
            if watermark_data:
                img = encode_lsb_watermark(img, watermark_data)
            
            img_bytes = pil_to_png_bytes(img)
            zf.writestr(filename, img_bytes)
    
    zip_buf.seek(0)
    return zip_buf.getvalue()

def batch_generate_svg(items: List[Dict[str, Any]], default_options: Dict = None) -> bytes:
    zip_buf = io.BytesIO()
    
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for idx, item in enumerate(items):
            content = item.get('content', '')
            if not content:
                continue
            
            options = dict(default_options or {})
            options.update(item.get('options', {}))
            
            filename = item.get('filename', f'qr_{idx + 1}.svg')
            if not filename.endswith('.svg'):
                filename += '.svg'
            
            svg_content = generate_svg(
                content=content,
                error_correction=options.get('error_correction', 'M'),
                box_size=options.get('box_size', 10),
                border=options.get('border', 4),
                fg_color=options.get('fg_color', '#000000'),
                bg_color=options.get('bg_color', '#FFFFFF'),
                transparent_bg=options.get('transparent_bg', False),
            )
            
            zf.writestr(filename, svg_content.encode('utf-8'))
    
    zip_buf.seek(0)
    return zip_buf.getvalue()

def batch_generate(items: List[Dict[str, Any]], format: str = 'png',
                   default_options: Dict = None) -> bytes:
    if format == 'png':
        return batch_generate_png(items, default_options)
    elif format == 'svg':
        return batch_generate_svg(items, default_options)
    else:
        return batch_generate_png(items, default_options)
