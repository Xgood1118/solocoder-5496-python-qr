import os
import io
import json
import base64
import hashlib
from datetime import datetime

from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from PIL import Image

from config import Config
from utils import (
    get_content_hash, is_url, is_wifi_content, parse_wifi_content,
    generate_wifi_content, generate_vcard_content, validate_hex_color,
    get_client_ip, timestamp_now, format_timestamp
)
from qr_generator import (
    generate_qr_pil, pil_to_png_bytes, generate_svg, generate_pdf,
    get_qr_version, STYLE_SQUARE, STYLE_ROUNDED, STYLE_DOTS,
    STYLE_CLASSY, STYLE_CLASSY_DOTS
)
from qr_scanner import scan_qr_from_image, annotate_image_with_qr
from encryption import encrypt_content, decrypt_content, is_encrypted_qr, get_key_hash
from url_safety import check_url_safety, SAFE, SUSPICIOUS, DANGEROUS
from watermark import (
    encode_lsb_watermark, decode_lsb_watermark,
    create_watermark_data, embed_watermark_to_png, extract_watermark_from_png
)
from batch_generator import batch_generate
from stats_db import StatsDB

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

stats_db = None
if Config.ENABLE_STATS:
    stats_db = StatsDB(Config.STATS_DB_PATH)


def _get_content_type(content: str) -> str:
    if is_encrypted_qr(content):
        return 'encrypted'
    if is_url(content):
        return 'url'
    if is_wifi_content(content):
        return 'wifi'
    if content.startswith('BEGIN:VCARD'):
        return 'vcard'
    if content.startswith('MECARD:'):
        return 'mecard'
    return 'text'


def _validate_color(color: str, default: str) -> str:
    if not color:
        return default
    if validate_hex_color(color):
        return color
    return default


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'service': 'qr-service',
        'timestamp': timestamp_now(),
        'time_str': format_timestamp(timestamp_now()),
        'stats_enabled': Config.ENABLE_STATS,
    })


@app.route('/api/generate', methods=['POST'])
def generate_qr():
    data = request.get_json() or {}
    
    content_type = data.get('content_type', 'text')
    content = data.get('content', '')
    
    if not content and content_type == 'text':
        return jsonify({'error': 'content is required'}), 400
    
    if content_type == 'wifi':
        ssid = data.get('ssid', '')
        password = data.get('password', '')
        auth_type = data.get('auth_type', 'WPA')
        hidden = data.get('hidden', False)
        if not ssid:
            return jsonify({'error': 'ssid is required for wifi type'}), 400
        content = generate_wifi_content(ssid, password, auth_type, hidden)
    elif content_type == 'vcard':
        content = generate_vcard_content(
            fn=data.get('fn', ''),
            org=data.get('org', ''),
            title=data.get('title', ''),
            phone=data.get('phone', ''),
            email=data.get('email', ''),
            url=data.get('url', ''),
            note=data.get('note', ''),
        )
    elif content_type == 'encrypted':
        secret = data.get('secret', '')
        if not secret:
            return jsonify({'error': 'secret is required for encrypted type'}), 400
        plain_content = data.get('plain_content', '')
        if not plain_content:
            return jsonify({'error': 'plain_content is required for encrypted type'}), 400
        content = encrypt_content(plain_content, secret, Config.ENCRYPTION_KEY_SALT)
    
    output_format = data.get('format', 'png').lower()
    if output_format not in ('png', 'svg', 'pdf'):
        return jsonify({'error': 'format must be png, svg, or pdf'}), 400
    
    error_correction = data.get('error_correction', Config.DEFAULT_ERROR_CORRECTION).upper()
    if error_correction not in ('L', 'M', 'Q', 'H'):
        error_correction = Config.DEFAULT_ERROR_CORRECTION
    
    box_size = int(data.get('box_size', Config.DEFAULT_BOX_SIZE))
    border = int(data.get('border', Config.DEFAULT_BORDER))
    style = data.get('style', STYLE_SQUARE)
    if style not in (STYLE_SQUARE, STYLE_ROUNDED, STYLE_DOTS, STYLE_CLASSY, STYLE_CLASSY_DOTS):
        style = STYLE_SQUARE
    
    fg_color = _validate_color(data.get('fg_color'), '#000000')
    bg_color = _validate_color(data.get('bg_color'), '#FFFFFF')
    transparent_bg = bool(data.get('transparent_bg', False))
    
    gradient_start = data.get('gradient_start')
    gradient_end = data.get('gradient_end')
    gradient_direction = data.get('gradient_direction', 'vertical')
    if gradient_direction not in ('vertical', 'horizontal', 'diagonal'):
        gradient_direction = 'vertical'
    
    logo_image = None
    logo_data = data.get('logo_data')
    if logo_data:
        try:
            logo_bytes = base64.b64decode(logo_data)
            logo_image = Image.open(io.BytesIO(logo_bytes))
        except Exception as e:
            return jsonify({'error': f'invalid logo_data: {str(e)}'}), 400
    
    logo_ratio = float(data.get('logo_ratio', 0.2))
    if logo_ratio > Config.LOGO_MAX_AREA_RATIO:
        logo_ratio = Config.LOGO_MAX_AREA_RATIO
    
    if logo_image is not None:
        error_correction = 'H'
    
    watermark_enabled = bool(data.get('watermark', True))
    client_ip = get_client_ip(request)
    content_hash = get_content_hash(content)
    qr_version = get_qr_version(content, error_correction)
    
    if output_format == 'png':
        img = generate_qr_pil(
            content=content,
            error_correction=error_correction,
            box_size=box_size,
            border=border,
            style=style,
            fg_color=fg_color,
            bg_color=bg_color,
            transparent_bg=transparent_bg,
            gradient_start=gradient_start,
            gradient_end=gradient_end,
            gradient_direction=gradient_direction,
            logo_image=logo_image,
            logo_ratio=logo_ratio,
        )
        
        if watermark_enabled:
            wm_data = create_watermark_data(
                client_ip=client_ip,
                timestamp=timestamp_now(),
                content_hash=content_hash,
            )
            img = encode_lsb_watermark(img, wm_data)
        
        img_bytes = pil_to_png_bytes(img)
        
        if stats_db:
            stats_db.record_generation(
                content=content,
                content_type=_get_content_type(content),
                style=style,
                fmt='png',
                has_logo=logo_image is not None,
                error_correction=error_correction,
                size=img.size[0],
                client_ip=client_ip,
                user_agent=request.headers.get('User-Agent', ''),
            )
        
        return send_file(
            io.BytesIO(img_bytes),
            mimetype='image/png',
            as_attachment=False,
        )
    
    elif output_format == 'svg':
        svg_content = generate_svg(
            content=content,
            error_correction=error_correction,
            box_size=box_size,
            border=border,
            fg_color=fg_color,
            bg_color=bg_color,
            transparent_bg=transparent_bg,
            logo_image=logo_image,
        )
        
        if stats_db:
            version = get_qr_version(content, error_correction)
            qr_size = (version * 4 + 17 + 2 * border) * box_size
            stats_db.record_generation(
                content=content,
                content_type=_get_content_type(content),
                style=style,
                fmt='svg',
                has_logo=logo_image is not None,
                error_correction=error_correction,
                size=qr_size,
                client_ip=client_ip,
                user_agent=request.headers.get('User-Agent', ''),
            )
        
        return Response(svg_content, mimetype='image/svg+xml')
    
    elif output_format == 'pdf':
        pdf_bytes = generate_pdf(
            content=content,
            error_correction=error_correction,
            box_size=box_size,
            border=border,
            fg_color=fg_color,
            bg_color=bg_color,
            logo_image=logo_image,
        )
        
        if stats_db:
            stats_db.record_generation(
                content=content,
                content_type=_get_content_type(content),
                style=style,
                fmt='pdf',
                has_logo=logo_image is not None,
                error_correction=error_correction,
                size=0,
                client_ip=client_ip,
                user_agent=request.headers.get('User-Agent', ''),
            )
        
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name='qrcode.pdf',
        )


@app.route('/api/generate/batch', methods=['POST'])
def batch_generate_qr():
    data = request.get_json() or {}
    
    items = data.get('items', [])
    if not items or not isinstance(items, list):
        return jsonify({'error': 'items array is required'}), 400
    
    if len(items) > 100:
        return jsonify({'error': 'maximum 100 items per batch'}), 400
    
    output_format = data.get('format', 'png').lower()
    if output_format not in ('png', 'svg'):
        return jsonify({'error': 'batch format must be png or svg'}), 400
    
    default_options = {
        'error_correction': data.get('error_correction', Config.DEFAULT_ERROR_CORRECTION),
        'box_size': data.get('box_size', Config.DEFAULT_BOX_SIZE),
        'border': data.get('border', Config.DEFAULT_BORDER),
        'style': data.get('style', STYLE_SQUARE),
        'fg_color': data.get('fg_color', '#000000'),
        'bg_color': data.get('bg_color', '#FFFFFF'),
        'transparent_bg': data.get('transparent_bg', False),
        'logo_ratio': data.get('logo_ratio', 0.2),
    }
    
    client_ip = get_client_ip(request)
    watermark_enabled = bool(data.get('watermark', True))
    
    processed_items = []
    for item in items:
        content = item.get('content', '')
        if not content:
            continue
        
        item_options = dict(default_options)
        
        if watermark_enabled:
            content_hash = get_content_hash(content)
            wm_data = create_watermark_data(
                client_ip=client_ip,
                timestamp=timestamp_now(),
                content_hash=content_hash,
            )
            item_options['watermark_data'] = wm_data
        
        processed_items.append({
            'content': content,
            'filename': item.get('filename', ''),
            'options': item_options,
        })
    
    zip_bytes = batch_generate(processed_items, format=output_format, default_options=default_options)
    
    if stats_db:
        for item in items:
            content = item.get('content', '')
            if content:
                stats_db.record_generation(
                    content=content,
                    content_type=_get_content_type(content),
                    style=default_options.get('style', STYLE_SQUARE),
                    fmt=output_format,
                    has_logo=False,
                    error_correction=default_options.get('error_correction', Config.DEFAULT_ERROR_CORRECTION),
                    size=0,
                    client_ip=client_ip,
                    user_agent=request.headers.get('User-Agent', ''),
                )
    
    return send_file(
        io.BytesIO(zip_bytes),
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'qrcodes_{output_format}.zip',
    )


@app.route('/api/scan', methods=['POST'])
def scan_qr():
    if 'image' not in request.files:
        return jsonify({'error': 'no image file provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'empty filename'}), 400
    
    try:
        image_bytes = file.read()
    except Exception as e:
        return jsonify({'error': f'failed to read image: {str(e)}'}), 400
    
    denoise = request.args.get('denoise', 'true').lower() == 'true'
    binarize = request.args.get('binarize', 'false').lower() == 'true'
    rotate = request.args.get('rotate', 'true').lower() == 'true'
    
    result = scan_qr_from_image(image_bytes, denoise=denoise, binarize=binarize, rotate=rotate)
    
    client_ip = get_client_ip(request)
    
    for qr_result in result.get('results', []):
        content = qr_result.get('data', '')
        content_type = _get_content_type(content)
        qr_result['content_type'] = content_type
        
        if content_type == 'url':
            qr_result['url_safety'] = check_url_safety(content)
        elif content_type == 'wifi':
            qr_result['wifi_info'] = parse_wifi_content(content)
            qr_result['requires_confirmation'] = True
        elif content_type == 'encrypted':
            qr_result['is_encrypted'] = True
        
        if is_url(content):
            qr_result['url_safety'] = check_url_safety(content)
        
        if stats_db:
            freq_info = stats_db.record_scan(
                content=content,
                content_type=content_type,
                qr_count=result.get('count', 1),
                client_ip=client_ip,
                user_agent=request.headers.get('User-Agent', ''),
            )
            qr_result['frequency'] = freq_info
    
    result['watermark'] = extract_watermark_from_png(image_bytes)
    
    return jsonify(result)


@app.route('/api/scan/decrypt', methods=['POST'])
def decrypt_scanned_qr():
    data = request.get_json() or {}
    
    content = data.get('content', '')
    secret = data.get('secret', '')
    
    if not content:
        return jsonify({'error': 'content is required'}), 400
    if not secret:
        return jsonify({'error': 'secret is required'}), 400
    
    result = decrypt_content(content, secret, Config.ENCRYPTION_KEY_SALT)
    
    if result['success'] and result['content']:
        decrypted = result['content']
        result['content_type'] = _get_content_type(decrypted)
        
        if is_url(decrypted):
            result['url_safety'] = check_url_safety(decrypted)
        elif is_wifi_content(decrypted):
            result['wifi_info'] = parse_wifi_content(decrypted)
            result['requires_confirmation'] = True
    
    return jsonify(result)


@app.route('/api/url/check', methods=['POST'])
def check_url():
    data = request.get_json() or {}
    url = data.get('url', '')
    
    if not url:
        return jsonify({'error': 'url is required'}), 400
    
    result = check_url_safety(url)
    return jsonify(result)


@app.route('/api/watermark/extract', methods=['POST'])
def extract_watermark():
    if 'image' not in request.files:
        return jsonify({'error': 'no image file provided'}), 400
    
    file = request.files['image']
    try:
        image_bytes = file.read()
    except Exception as e:
        return jsonify({'error': f'failed to read image: {str(e)}'}), 400
    
    result = extract_watermark_from_png(image_bytes)
    return jsonify(result)


@app.route('/api/stats', methods=['GET'])
def get_stats():
    if not stats_db:
        return jsonify({'error': 'stats are disabled'}), 404
    
    days = int(request.args.get('days', 7))
    
    gen_stats = stats_db.get_generation_stats(days)
    scan_stats = stats_db.get_scan_stats(days)
    top_scanned = stats_db.get_top_scanned(limit=10, days=days)
    
    return jsonify({
        'generation': gen_stats,
        'scan': scan_stats,
        'top_scanned': top_scanned,
    })


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    if not stats_db:
        return jsonify({'error': 'stats are disabled'}), 404
    
    limit = int(request.args.get('limit', 20))
    alerts = stats_db.get_recent_alerts(limit)
    
    return jsonify({
        'count': len(alerts),
        'alerts': alerts,
    })


@app.route('/api/equivalent', methods=['POST'])
def check_equivalent():
    data = request.get_json() or {}
    contents = data.get('contents', [])
    
    if not contents or not isinstance(contents, list):
        return jsonify({'error': 'contents array is required'}), 400
    
    hashes = {}
    for i, content in enumerate(contents):
        content_hash = get_content_hash(content)
        if content_hash not in hashes:
            hashes[content_hash] = []
        hashes[content_hash].append(i)
    
    groups = [indices for indices in hashes.values() if len(indices) > 1]
    
    return jsonify({
        'total': len(contents),
        'equivalent_groups': groups,
        'unique_hashes': len(hashes),
    })


@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'connected', 'message': 'QR scanner WebSocket ready'})


@socketio.on('disconnect')
def handle_disconnect():
    pass


@socketio.on('scan_frame')
def handle_scan_frame(data):
    try:
        image_data = data.get('image', '')
        if not image_data:
            emit('scan_result', {'success': False, 'error': 'no image data'})
            return
        
        if image_data.startswith('data:image'):
            image_data = image_data.split(',', 1)[1]
        
        image_bytes = base64.b64decode(image_data)
        result = scan_qr_from_image(image_bytes, denoise=True, binarize=False, rotate=True)
        
        client_ip = request.remote_addr or 'unknown'
        
        for qr_result in result.get('results', []):
            content = qr_result.get('data', '')
            content_type = _get_content_type(content)
            qr_result['content_type'] = content_type
            
            if is_url(content):
                qr_result['url_safety'] = check_url_safety(content)
            
            if stats_db:
                freq_info = stats_db.record_scan(
                    content=content,
                    content_type=content_type,
                    qr_count=result.get('count', 1),
                    client_ip=client_ip,
                    user_agent='websocket',
                )
                qr_result['frequency'] = freq_info
        
        emit('scan_result', result)
    except Exception as e:
        emit('scan_result', {'success': False, 'error': str(e)})


@socketio.on('start_stream')
def handle_start_stream(data):
    emit('stream_started', {'status': 'ok', 'message': 'Stream started'})


@socketio.on('stop_stream')
def handle_stop_stream():
    emit('stream_stopped', {'status': 'ok', 'message': 'Stream stopped'})


@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'file too large', 'max_size': f'{Config.MAX_CONTENT_LENGTH // (1024*1024)}MB'}), 413


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'not found'}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'method not allowed'}), 405


if __name__ == '__main__':
    print(f'QR Service starting on {Config.HOST}:{Config.PORT}')
    print(f'Stats enabled: {Config.ENABLE_STATS}')
    print(f'Debug: {Config.DEBUG}')
    socketio.run(app, host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
