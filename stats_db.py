import sqlite3
import hashlib
import time
from contextlib import contextmanager
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

class StatsDB:
    def __init__(self, db_path: str = 'qr_stats.db'):
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS qr_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT NOT NULL,
                    content_preview TEXT,
                    content_type TEXT,
                    style TEXT,
                    format TEXT,
                    has_logo INTEGER DEFAULT 0,
                    error_correction TEXT,
                    size INTEGER,
                    client_ip TEXT,
                    user_agent TEXT,
                    created_at INTEGER NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS qr_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT NOT NULL,
                    content_preview TEXT,
                    content_type TEXT,
                    qr_count INTEGER,
                    client_ip TEXT,
                    user_agent TEXT,
                    created_at INTEGER NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scan_frequency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT NOT NULL,
                    time_window INTEGER NOT NULL,
                    scan_count INTEGER DEFAULT 0,
                    window_start INTEGER NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    content_hash TEXT,
                    message TEXT,
                    client_ip TEXT,
                    details TEXT,
                    created_at INTEGER NOT NULL
                )
            ''')
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gen_content ON qr_generations(content_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gen_time ON qr_generations(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_content ON qr_scans(content_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_time ON qr_scans(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_freq_content ON scan_frequency(content_hash, window_start)')
    
    def record_generation(self, content: str, content_type: str, style: str,
                          fmt: str, has_logo: bool, error_correction: str,
                          size: int, client_ip: str, user_agent: str = ''):
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        content_preview = content[:100] if content else ''
        now = int(time.time())
        
        with self._get_conn() as conn:
            conn.execute('''
                INSERT INTO qr_generations
                (content_hash, content_preview, content_type, style, format,
                 has_logo, error_correction, size, client_ip, user_agent, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (content_hash, content_preview, content_type, style, fmt,
                  int(has_logo), error_correction, size, client_ip, user_agent, now))
    
    def record_scan(self, content: str, content_type: str, qr_count: int,
                    client_ip: str, user_agent: str = '') -> dict:
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        content_preview = content[:100] if content else ''
        now = int(time.time())
        
        with self._get_conn() as conn:
            conn.execute('''
                INSERT INTO qr_scans
                (content_hash, content_preview, content_type, qr_count,
                 client_ip, user_agent, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (content_hash, content_preview, content_type, qr_count,
                  client_ip, user_agent, now))
            
            return self._check_frequency(conn, content_hash, now, client_ip)
    
    def _check_frequency(self, conn, content_hash: str, now: int, client_ip: str) -> dict:
        window_seconds = 60
        window_start = now - (now % window_seconds)
        
        cursor = conn.execute('''
            SELECT id, scan_count FROM scan_frequency
            WHERE content_hash = ? AND window_start = ?
        ''', (content_hash, window_start))
        
        row = cursor.fetchone()
        
        if row:
            new_count = row['scan_count'] + 1
            conn.execute('''
                UPDATE scan_frequency SET scan_count = ? WHERE id = ?
            ''', (new_count, row['id']))
        else:
            new_count = 1
            conn.execute('''
                INSERT INTO scan_frequency (content_hash, time_window, scan_count, window_start)
                VALUES (?, ?, ?, ?)
            ''', (content_hash, window_seconds, 1, window_start))
        
        is_high_freq = new_count >= 100
        
        if is_high_freq and new_count == 100:
            conn.execute('''
                INSERT INTO alerts (alert_type, content_hash, message, client_ip, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('high_frequency_scan', content_hash,
                  f'High frequency scan detected: {new_count} scans in {window_seconds}s',
                  client_ip, f'scan_count={new_count}, window={window_seconds}s', now))
        
        return {
            'scan_count': new_count,
            'window_seconds': window_seconds,
            'is_high_frequency': is_high_freq,
        }
    
    def get_generation_stats(self, days: int = 7) -> Dict[str, Any]:
        end_time = int(time.time())
        start_time = end_time - days * 86400
        
        with self._get_conn() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) as total,
                       COUNT(DISTINCT content_hash) as unique_contents
                FROM qr_generations
                WHERE created_at >= ?
            ''', (start_time,))
            row = cursor.fetchone()
            
            cursor = conn.execute('''
                SELECT format, COUNT(*) as count
                FROM qr_generations
                WHERE created_at >= ?
                GROUP BY format
                ORDER BY count DESC
            ''', (start_time,))
            by_format = [dict(r) for r in cursor.fetchall()]
            
            cursor = conn.execute('''
                SELECT content_type, COUNT(*) as count
                FROM qr_generations
                WHERE created_at >= ?
                GROUP BY content_type
                ORDER BY count DESC
            ''', (start_time,))
            by_type = [dict(r) for r in cursor.fetchall()]
            
            return {
                'period_days': days,
                'total_generations': row['total'],
                'unique_contents': row['unique_contents'],
                'by_format': by_format,
                'by_content_type': by_type,
            }
    
    def get_scan_stats(self, days: int = 7) -> Dict[str, Any]:
        end_time = int(time.time())
        start_time = end_time - days * 86400
        
        with self._get_conn() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) as total,
                       COUNT(DISTINCT content_hash) as unique_contents,
                       SUM(qr_count) as total_qr_codes
                FROM qr_scans
                WHERE created_at >= ?
            ''', (start_time,))
            row = cursor.fetchone()
            
            cursor = conn.execute('''
                SELECT content_type, COUNT(*) as count
                FROM qr_scans
                WHERE created_at >= ?
                GROUP BY content_type
                ORDER BY count DESC
            ''', (start_time,))
            by_type = [dict(r) for r in cursor.fetchall()]
            
            return {
                'period_days': days,
                'total_scans': row['total'] or 0,
                'unique_contents': row['unique_contents'] or 0,
                'total_qr_codes': row['total_qr_codes'] or 0,
                'by_content_type': by_type,
            }
    
    def get_recent_alerts(self, limit: int = 20) -> List[Dict]:
        with self._get_conn() as conn:
            cursor = conn.execute('''
                SELECT * FROM alerts
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            return [dict(r) for r in cursor.fetchall()]
    
    def get_top_scanned(self, limit: int = 10, days: int = 7) -> List[Dict]:
        end_time = int(time.time())
        start_time = end_time - days * 86400
        
        with self._get_conn() as conn:
            cursor = conn.execute('''
                SELECT content_hash, content_preview, content_type,
                       COUNT(*) as scan_count
                FROM qr_scans
                WHERE created_at >= ?
                GROUP BY content_hash
                ORDER BY scan_count DESC
                LIMIT ?
            ''', (start_time, limit))
            return [dict(r) for r in cursor.fetchall()]
