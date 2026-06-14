import io
import cv2
import numpy as np
from PIL import Image
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol
from typing import List, Dict, Any, Optional

ERROR_LEVEL_NAMES = {
    0: 'L (7%)',
    1: 'M (15%)',
    2: 'Q (25%)',
    3: 'H (30%)',
}

def preprocess_image(image: np.ndarray, denoise: bool = True, binarize: bool = False,
                     rotate: bool = True) -> np.ndarray:
    img = image.copy()
    
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    
    if denoise:
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.medianBlur(gray, 3)
    
    if binarize:
        gray = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    if rotate:
        gray = _correct_rotation(gray, img if len(img.shape) == 3 else None)
    
    return gray

def _correct_rotation(gray: np.ndarray, color_img: Optional[np.ndarray] = None) -> np.ndarray:
    coords = np.column_stack(np.where(gray < 128))
    if len(coords) == 0:
        return gray
    
    try:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        if abs(angle) > 0.5:
            (h, w) = gray.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            gray = cv2.warpAffine(gray, M, (w, h),
                                  flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
    except:
        pass
    
    return gray

def decode_qr_codes(image: np.ndarray) -> List[Dict[str, Any]]:
    results = []
    
    decoded_objects = pyzbar.decode(image, symbols=[ZBarSymbol.QRCODE])
    
    for obj in decoded_objects:
        points = obj.polygon
        if len(points) >= 4:
            pts = np.array([[p.x, p.y] for p in points], dtype=np.int32)
            rect = cv2.boundingRect(pts)
        else:
            rect = (obj.rect.left, obj.rect.top, obj.rect.width, obj.rect.height)
            pts = None
        
        try:
            data = obj.data.decode('utf-8')
        except UnicodeDecodeError:
            data = obj.data.decode('latin-1', errors='replace')
        
        result = {
            'data': data,
            'type': obj.type,
            'rect': {
                'x': rect[0],
                'y': rect[1],
                'width': rect[2],
                'height': rect[3],
            },
            'polygon': [[p.x, p.y] for p in points] if points else None,
            'quality': obj.quality if hasattr(obj, 'quality') else None,
        }
        results.append(result)
    
    return results

def scan_qr_from_image(image_bytes: bytes, denoise: bool = True, binarize: bool = False,
                       rotate: bool = True) -> Dict[str, Any]:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img_array = np.array(img)
        
        if len(img_array.shape) == 3 and img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        elif len(img_array.shape) == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        processed = preprocess_image(img_array, denoise=denoise, binarize=binarize, rotate=rotate)
        results = decode_qr_codes(processed)
        
        if not results:
            processed2 = preprocess_image(img_array, denoise=True, binarize=True, rotate=rotate)
            results = decode_qr_codes(processed2)
        
        if not results:
            results = decode_qr_codes(img_array)
        
        return {
            'success': True,
            'count': len(results),
            'results': results,
            'image_size': {
                'width': img.width,
                'height': img.height,
            }
        }
    except Exception as e:
        return {
            'success': False,
            'count': 0,
            'results': [],
            'error': str(e),
        }

def detect_qr_error_level(qr_img: Image.Image) -> Optional[str]:
    try:
        from qrcode import base
        from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
        
        img = qr_img.convert('L')
        width, height = img.size
        
        finder_pattern_size = 7
        quiet_zone = 4
        
        version = _detect_version(img)
        if version:
            return f'Version {version}'
        
        return None
    except:
        return None

def _detect_version(img: Image.Image) -> Optional[int]:
    try:
        width, height = img.size
        
        top_left = _find_finder_pattern(img, 0, 0, width // 2, height // 2)
        if not top_left:
            return None
        
        module_size = top_left['size'] / 7
        
        total_modules = int(round(width / module_size))
        version = (total_modules - 17) // 4
        
        if 1 <= version <= 40:
            return version
        
        return None
    except:
        return None

def _find_finder_pattern(img: Image.Image, x: int, y: int, w: int, h: int) -> Optional[Dict]:
    pixels = img.load()
    
    for start_y in range(y, y + h - 10):
        for start_x in range(x, x + w - 10):
            if pixels[start_x, start_y] < 128:
                size = 0
                for dx in range(1, min(w - start_x, h - start_y)):
                    if pixels[start_x + dx, start_y + dx] < 128:
                        size = dx
                    else:
                        break
                if size > 10:
                    return {'x': start_x, 'y': start_y, 'size': size}
    return None

def annotate_image_with_qr(image_bytes: bytes, results: List[Dict]) -> bytes:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img_array = np.array(img)
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        for i, result in enumerate(results):
            rect = result['rect']
            x, y, w, h = rect['x'], rect['y'], rect['width'], rect['height']
            
            cv2.rectangle(img_array, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            label = f'QR-{i+1}'
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
            
            cv2.rectangle(img_array, (x, y - text_h - 10), (x + text_w + 10, y), (0, 255, 0), -1)
            cv2.putText(img_array, label, (x + 5, y - 5), font, font_scale, (255, 255, 255), thickness)
        
        _, buf = cv2.imencode('.png', img_array)
        return buf.tobytes()
    except Exception as e:
        return image_bytes
