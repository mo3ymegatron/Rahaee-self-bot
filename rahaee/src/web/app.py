# src/web/app.py

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from functools import wraps
import asyncio
import threading
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets

from core.logger import get_logger
from core.database import Database
from core.config import Config


class WebApp:
    """کلاس مدیریت وب پنل رهایی"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger("web_app")
        self.db = bot.db
        self.config = bot.config
        self.client = bot.client
        
        # ایجاد اپلیکیشن Flask
        self.app = Flask(__name__)
        self.app.secret_key = self.config.WEB_SECRET_KEY
        
        # تنظیمات
        self.app.config['SESSION_TYPE'] = 'filesystem'
        self.app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
        
        # CORS
        CORS(self.app)
        
        # WebSocket
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # ثبت مسیرها
        self._register_routes()
        self._register_socket_events()
        
        # لاگین کاربران
        self.logged_in_users = {}
        
    def _register_routes(self):
        """ثبت مسیرهای وب"""
        
        # ============================================================
        # دکوریتورهای احراز هویت
        # ============================================================
        
        def login_required(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if 'user_id' not in session:
                    return redirect(url_for('login'))
                return f(*args, **kwargs)
            return decorated_function
        
        def owner_required(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if 'user_id' not in session:
                    return redirect(url_for('login'))
                if session.get('user_id') != self.config.OWNER_ID:
                    return jsonify({'error': 'دسترسی غیرمجاز'}), 403
                return f(*args, **kwargs)
            return decorated_function
        
        # ============================================================
        # مسیرهای اصلی
        # ============================================================
        
        @self.app.route('/')
        def index():
            """صفحه اصلی"""
            if 'user_id' in session:
                return redirect(url_for('dashboard'))
            return redirect(url_for('login'))
            
        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            """صفحه ورود"""
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                
                # بررسی اعتبار
                if self._verify_login(username, password):
                    session['user_id'] = self.config.OWNER_ID
                    session['username'] = username
                    session.permanent = True
                    return redirect(url_for('dashboard'))
                else:
                    return render_template('login.html', error='نام کاربری یا رمز عبور اشتباه است')
                    
            return render_template('login.html')
            
        @self.app.route('/logout')
        def logout():
            """خروج از سیستم"""
            session.clear()
            return redirect(url_for('login'))
            
        @self.app.route('/dashboard')
        @login_required
        def dashboard():
            """داشبورد اصلی"""
            return render_template('dashboard.html', user=session.get('username'))
            
        @self.app.route('/users')
        @login_required
        def users():
            """مدیریت کاربران"""
            return render_template('users.html', user=session.get('username'))
            
        @self.app.route('/settings')
        @login_required
        def settings():
            """تنظیمات"""
            return render_template('settings.html', user=session.get('username'))
            
        # ============================================================
        # API مسیرها
        # ============================================================
        
        @self.app.route('/api/stats')
        @login_required
        def api_stats():
            """API دریافت آمار"""
            try:
                # دریافت آمار
                total_stats = asyncio.run(self.db.get_total_stats())
                daily_stats = asyncio.run(self.db.get_daily_stats())
                
                # آمار آنلاین
                online_users = len(self.socketio.server.rooms.get('/', {}).keys())
                
                return jsonify({
                    'success': True,
                    'data': {
                        'total_users': total_stats.get('total_users', 0),
                        'total_groups': total_stats.get('total_groups', 0),
                        'total_messages': total_stats.get('total_messages', 0),
                        'messages_today': daily_stats.get('messages_sent', 0),
                        'commands_today': daily_stats.get('commands_used', 0),
                        'new_users_today': daily_stats.get('new_users', 0),
                        'online_users': online_users,
                        'uptime': self.bot.get_uptime(),
                        'version': self.config.BOT_VERSION
                    }
                })
            except Exception as e:
                self.logger.error(f"API stats error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
        @self.app.route('/api/users')
        @login_required
        def api_users():
            """API دریافت لیست کاربران"""
            try:
                page = int(request.args.get('page', 1))
                per_page = int(request.args.get('per_page', 20))
                
                users = asyncio.run(self.db.get_all_users())
                
                # صفحه‌بندی
                start = (page - 1) * per_page
                end = start + per_page
                page_users = users[start:end]
                
                # دریافت اطلاعات کامل کاربران
                user_list = []
                for user in page_users:
                    user_info = asyncio.run(self.client.get_user_info(user['id']))
                    user_list.append({
                        'id': user['id'],
                        'username': user_info.username if user_info else None,
                        'first_name': user_info.first_name if user_info else 'نامشخص',
                        'last_name': user_info.last_name if user_info else '',
                        'is_admin': user.get('is_admin', False),
                        'is_banned': user.get('is_banned', False),
                        'message_count': user.get('message_count', 0),
                        'command_count': user.get('command_count', 0),
                        'created_at': user.get('created_at'),
                        'last_seen': user.get('last_seen')
                    })
                    
                return jsonify({
                    'success': True,
                    'data': {
                        'users': user_list,
                        'total': len(users),
                        'page': page,
                        'per_page': per_page,
                        'total_pages': (len(users) + per_page - 1) // per_page
                    }
                })
            except Exception as e:
                self.logger.error(f"API users error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
        @self.app.route('/api/user/<int:user_id>')
        @login_required
        def api_user_detail(user_id):
            """API دریافت اطلاعات یک کاربر"""
            try:
                user = asyncio.run(self.db.get_user(user_id))
                if not user:
                    return jsonify({'success': False, 'error': 'کاربر یافت نشد'}), 404
                    
                user_info = asyncio.run(self.client.get_user_info(user_id))
                
                return jsonify({
                    'success': True,
                    'data': {
                        'id': user['id'],
                        'username': user_info.username if user_info else None,
                        'first_name': user_info.first_name if user_info else 'نامشخص',
                        'last_name': user_info.last_name if user_info else '',
                        'phone': user_info.phone_number if user_info else None,
                        'is_admin': user.get('is_admin', False),
                        'is_banned': user.get('is_banned', False),
                        'message_count': user.get('message_count', 0),
                        'command_count': user.get('command_count', 0),
                        'created_at': user.get('created_at'),
                        'last_seen': user.get('last_seen'),
                        'bio': user.get('bio', ''),
                        'balance': user.get('balance', 0),
                        'expir_date': user.get('expir_date')
                    }
                })
            except Exception as e:
                self.logger.error(f"API user detail error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
        @self.app.route('/api/user/<int:user_id>/ban', methods=['POST'])
        @owner_required
        def api_ban_user(user_id):
            """API بلاک کاربر"""
            try:
                asyncio.run(self.db.update_user(user_id, is_banned=True))
                return jsonify({'success': True, 'message': 'کاربر با موفقیت بلاک شد'})
            except Exception as e:
                self.logger.error(f"API ban user error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
        @self.app.route('/api/user/<int:user_id>/unban', methods=['POST'])
        @owner_required
        def api_unban_user(user_id):
            """API آنبلاک کاربر"""
            try:
                asyncio.run(self.db.update_user(user_id, is_banned=False))
                return jsonify({'success': True, 'message': 'کاربر با موفقیت آنبلاک شد'})
            except Exception as e:
                self.logger.error(f"API unban user error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
        @self.app.route('/api/user/<int:user_id>/admin', methods=['POST'])
        @owner_required
        def api_make_admin(user_id):
            """API افزودن مدیر"""
            try:
                asyncio.run(self.db.update_user(user_id, is_admin=True))
                return jsonify({'success': True, 'message': 'کاربر با موفقیت مدیر شد'})
            except Exception as e:
                self.logger.error(f"API make admin error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
        @self.app.route('/api/user/<int:user_id>/admin', methods=['DELETE'])
        @owner_required
        def api_remove_admin(user_id):
            """API حذف مدیر"""
            try:
                asyncio.run(self.db.update_user(user_id, is_admin=False))
                return jsonify({'success': True, 'message': 'دسترسی مدیر با موفقیت حذف شد'})
            except Exception as e:
                self.logger.error(f"API remove admin error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
        @self.app.route('/api/settings', methods=['GET', 'POST'])
        @login_required
        def api_settings():
            """API تنظیمات"""
            if request.method == 'GET':
                try:
                    # دریافت تنظیمات
                    settings = {
                        'bot_name': asyncio.run(self.db.get_setting('bot_name', 'رهایی')),
                        'bot_language': asyncio.run(self.db.get_setting('bot_language', 'fa')),
                        'auto_reply': asyncio.run(self.db.get_setting('auto_reply', False)),
                        'anti_spam': asyncio.run(self.db.get_setting('anti_spam', True)),
                        'anti_links': asyncio.run(self.db.get_setting('anti_links', False)),
                        'force_join': asyncio.run(self.db.get_setting('force_join', False)),
                        'welcome_message': asyncio.run(self.db.get_setting('welcome_message', '')),
                        'log_level': asyncio.run(self.db.get_setting('log_level', 'INFO'))
                    }
                    return jsonify({'success': True, 'data': settings})
                except Exception as e:
                    self.logger.error(f"API get settings error: {e}")
                    return jsonify({'success': False, 'error': str(e)}), 500
                    
            elif request.method == 'POST':
                try:
                    data = request.json
                    for key, value in data.items():
                        asyncio.run(self.db.set_setting(key, value))
                    return jsonify({'success': True, 'message': 'تنظیمات با موفقیت ذخیره شد'})
                except Exception as e:
                    self.logger.error(f"API save settings error: {e}")
                    return jsonify({'success': False, 'error': str(e)}), 500
                    
        @self.app.route('/api/backup', methods=['POST'])
        @owner_required
        def api_backup():
            """API بکاپ‌گیری"""
            try:
                # اجرای بکاپ
                import shutil
                from pathlib import Path
                
                backup_dir = Path("data/backups")
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = backup_dir / f"backup_{timestamp}.db"
                
                shutil.copy2(self.config.DB_PATH, backup_file)
                
                return jsonify({
                    'success': True,
                    'message': 'بکاپ با موفقیت گرفته شد',
                    'data': {
                        'filename': backup_file.name,
                        'size': backup_file.stat().st_size,
                        'timestamp': timestamp
                    }
                })
            except Exception as e:
                self.logger.error(f"API backup error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
        @self.app.route('/api/logs')
        @owner_required
        def api_logs():
            """API دریافت لاگ‌ها"""
            try:
                lines = int(request.args.get('lines', 50))
                log_file = "logs/rahaee.log"
                
                if not os.path.exists(log_file):
                    return jsonify({'success': True, 'data': {'logs': 'لاگی موجود نیست'}})
                    
                with open(log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                    logs = ''.join(last_lines)
                    
                return jsonify({'success': True, 'data': {'logs': logs}})
            except Exception as e:
                self.logger.error(f"API logs error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
        @self.app.route('/api/restart', methods=['POST'])
        @owner_required
        def api_restart():
            """API ریستارت ربات"""
            try:
                # اجرای ریستارت در یک thread جدا
                def restart_bot():
                    import time
                    time.sleep(2)
                    asyncio.run(self.bot.restart())
                    
                threading.Thread(target=restart_bot).start()
                return jsonify({'success': True, 'message': 'ربات در حال ریستارت است...'})
            except Exception as e:
                self.logger.error(f"API restart error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
                
    def _register_socket_events(self):
        """ثبت رویدادهای WebSocket"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """اتصال WebSocket"""
            self.logger.info(f"🔌 WebSocket connected: {request.sid}")
            emit('connected', {'status': 'ok'})
            
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """قطع WebSocket"""
            self.logger.info(f"🔌 WebSocket disconnected: {request.sid}")
            
        @self.socketio.on('get_realtime_stats')
        def handle_realtime_stats():
            """دریافت آمار لحظه‌ای"""
            def send_stats():
                # دریافت آمار
                total_stats = asyncio.run(self.db.get_total_stats())
                daily_stats = asyncio.run(self.db.get_daily_stats())
                
                emit('realtime_stats', {
                    'total_users': total_stats.get('total_users', 0),
                    'total_messages': total_stats.get('total_messages', 0),
                    'messages_today': daily_stats.get('messages_sent', 0),
                    'commands_today': daily_stats.get('commands_used', 0),
                    'online_users': len(self.socketio.server.rooms.get('/', {}).keys()),
                    'uptime': self.bot.get_uptime()
                })
                
            # ارسال هر ۱۰ ثانیه
            send_stats()
            
    def _verify_login(self, username: str, password: str) -> bool:
        """بررسی اعتبار ورود"""
        # فقط مالک می‌تواند وارد شود
        if username == "admin" and password == self.config.WEB_SECRET_KEY:
            return True
        return False
        
    def run(self, host: str = None, port: int = None, debug: bool = None):
        """اجرای وب پنل"""
        host = host or self.config.WEB_HOST
        port = port or self.config.WEB_PORT
        debug = debug if debug is not None else self.config.WEB_DEBUG
        
        self.logger.info(f"🌐 Web panel running on http://{host}:{port}")
        self.socketio.run(self.app, host=host, port=port, debug=debug)
