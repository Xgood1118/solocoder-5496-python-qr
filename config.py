import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PORT = int(os.getenv('PORT', 5000))
    HOST = os.getenv('HOST', '0.0.0.0')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    ENABLE_STATS = os.getenv('ENABLE_STATS', 'True').lower() == 'true'
    STATS_DB_PATH = os.getenv('STATS_DB_PATH', 'qr_stats.db')
    
    HIGH_FREQ_THRESHOLD = int(os.getenv('HIGH_FREQ_THRESHOLD', 100))
    HIGH_FREQ_WINDOW = int(os.getenv('HIGH_FREQ_WINDOW', 60))
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    
    DEFAULT_ERROR_CORRECTION = 'M'
    DEFAULT_BOX_SIZE = 10
    DEFAULT_BORDER = 4
    
    LOGO_MAX_AREA_RATIO = 0.20
    
    ENCRYPTION_KEY_SALT = os.getenv('ENCRYPTION_KEY_SALT', 'qr-service-salt')
