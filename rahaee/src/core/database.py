# src/core/database.py

import sqlite3
import json
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
import aiosqlite
import pickle
import hashlib
import base64
from cryptography.fernet import Fernet
import os

from core.config import Config


class Database:
    """کلاس مدیریت دیتابیس پیشرفته با رمزنگاری و کش"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db_path = self.config.DB_PATH
        self.logger = logging.getLogger(__name__)
        self.connection = None
        self.cursor = None
        self.cache = {}
        self.cache_timeout = 300  # 5 دقیقه
        self.is_connected = False
        self.lock = asyncio.Lock()
        
        # رمزنگاری
        self.encryption_key = self._get_encryption_key()
        self.cipher = Fernet(self.encryption_key) if self.encryption_key else None
        
    def _get_encryption_key(self) -> bytes:
        """دریافت یا ایجاد کلید رمزنگاری"""
        key_file = Path("data/encryption.key")
        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(key_file, "wb") as f:
                f.write(key)
            return key
    
    async def connect(self) -> bool:
        """اتصال به دیتابیس با مدیریت خطا"""
        try:
            # ایجاد پوشه داده
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            # اتصال با WAL mode برای عملکرد بهتر
            self.connection = await aiosqlite.connect(
                self.db_path,
                isolation_level=None
            )
            
            # فعال‌سازی WAL mode
            await self.connection.execute("PRAGMA journal_mode=WAL")
            await self.connection.execute("PRAGMA synchronous=NORMAL")
            await self.connection.execute("PRAGMA cache_size=10000")
            await self.connection.execute("PRAGMA foreign_keys=ON")
            await self.connection.execute("PRAGMA temp_store=MEMORY")
            
            self.cursor = await self.connection.cursor()
            self.is_connected = True
            
            # ایجاد جداول
            await self._create_tables()
            
            # مهاجرت دیتابیس
            await self._migrate_database()
            
            # پاکسازی کش
            await self._cleanup_cache()
            
            self.logger.info(f"✅ Database connected successfully: {self.db_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Database connection failed: {e}")
            return False
            
    async def disconnect(self) -> bool:
        """قطع اتصال از دیتابیس"""
        try:
            if self.connection:
                await self.connection.commit()
                await self.connection.close()
                self.is_connected = False
                self.logger.info("✅ Database disconnected successfully")
            return True
        except Exception as e:
            self.logger.error(f"❌ Database disconnect failed: {e}")
            return False
            
    async def _create_tables(self):
        """ایجاد همه جداول اصلی"""
        
        # جدول کاربران
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                is_owner BOOLEAN DEFAULT 0,
                is_admin BOOLEAN DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                command_count INTEGER DEFAULT 0,
                expir_date TIMESTAMP,
                balance INTEGER DEFAULT 0
            )
        """)
        
        # جدول گروه‌ها
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY,
                title TEXT,
                username TEXT,
                member_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                welcome_enabled BOOLEAN DEFAULT 0,
                welcome_message TEXT,
                anti_spam BOOLEAN DEFAULT 0,
                anti_links BOOLEAN DEFAULT 0,
                anti_flood BOOLEAN DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول پیام‌ها
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                message_id INTEGER,
                text TEXT,
                is_outgoing BOOLEAN,
                is_edited BOOLEAN DEFAULT 0,
                is_deleted BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # جدول تنظیمات
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول افک (AFK)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS afk_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                since TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # جدول پاسخ‌های خودکار
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS auto_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                response TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول بکاپ‌ها
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول لاگ‌ها
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                module TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول آمار روزانه
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date DATE PRIMARY KEY,
                messages_sent INTEGER DEFAULT 0,
                messages_received INTEGER DEFAULT 0,
                commands_used INTEGER DEFAULT 0,
                new_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0
            )
        """)
        
        # ایجاد ایندکس‌ها
        await self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)"
        )
        await self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id)"
        )
        await self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )
        await self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_auto_replies_keyword ON auto_replies(keyword)"
        )
        await self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)"
        )
        
        await self.connection.commit()
        self.logger.info("✅ All tables created successfully")
        
    async def _migrate_database(self):
        """مهاجرت دیتابیس برای نسخه‌های جدید"""
        try:
            # بررسی نسخه دیتابیس
            version = await self.get_setting("db_version", "1.0.0")
            
            if version == "1.0.0":
                # اضافه کردن ستون‌های جدید
                try:
                    await self.connection.execute(
                        "ALTER TABLE users ADD COLUMN bio TEXT"
                    )
                except:
                    pass
                
                try:
                    await self.connection.execute(
                        "ALTER TABLE users ADD COLUMN avatar TEXT"
                    )
                except:
                    pass
                
                await self.set_setting("db_version", "1.1.0")
                self.logger.info("✅ Database migrated to version 1.1.0")
                
            # مهاجرت‌های بعدی...
            
        except Exception as e:
            self.logger.error(f"❌ Database migration failed: {e}")
            
    async def _cleanup_cache(self):
        """پاکسازی کش قدیمی"""
        try:
            # حذف رکوردهای قدیمی
            await self.connection.execute("""
                DELETE FROM logs 
                WHERE created_at < datetime('now', '-30 days')
            """)
            
            await self.connection.execute("""
                DELETE FROM messages 
                WHERE created_at < datetime('now', '-90 days')
            """)
            
            await self.connection.commit()
            self.logger.info("✅ Cache cleaned successfully")
        except Exception as e:
            self.logger.error(f"❌ Cache cleanup failed: {e}")
            
    def _cache_key(self, *args) -> str:
        """ساخت کلید کش"""
        return hashlib.md5(str(args).encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """دریافت از کش"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if (datetime.now() - timestamp).seconds < self.cache_timeout:
                return value
            else:
                del self.cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """ذخیره در کش"""
        self.cache[key] = (value, datetime.now())
        
    # ============================================================
    # متدهای کاربران
    # ============================================================
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """دریافت اطلاعات کاربر"""
        cache_key = self._cache_key("user", user_id)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        try:
            async with self.connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    user_dict = dict(result)
                    self._set_cache(cache_key, user_dict)
                    return user_dict
        except Exception as e:
            self.logger.error(f"Failed to get user {user_id}: {e}")
        return None
        
    async def create_user(self, user_id: int, **kwargs) -> bool:
        """ایجاد کاربر جدید"""
        try:
            # بررسی وجود کاربر
            if await self.get_user(user_id):
                return True
                
            query = """
                INSERT INTO users (id, username, first_name, last_name, phone, is_admin)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            
            await self.connection.execute(
                query,
                (
                    user_id,
                    kwargs.get("username", ""),
                    kwargs.get("first_name", ""),
                    kwargs.get("last_name", ""),
                    kwargs.get("phone", ""),
                    kwargs.get("is_admin", 0)
                )
            )
            
            await self.connection.commit()
            
            # پاکسازی کش
            self.cache.pop(self._cache_key("user", user_id), None)
            
            # ثبت آمار
            await self._update_daily_stats("new_users")
            
            self.logger.info(f"✅ User {user_id} created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create user {user_id}: {e}")
            return False
            
    async def update_user(self, user_id: int, **kwargs) -> bool:
        """به‌روزرسانی اطلاعات کاربر"""
        try:
            fields = []
            values = []
            
            for key, value in kwargs.items():
                fields.append(f"{key} = ?")
                values.append(value)
                
            if not fields:
                return True
                
            values.append(user_id)
            query = f"UPDATE users SET {', '.join(fields)} WHERE id = ?"
            
            await self.connection.execute(query, values)
            await self.connection.commit()
            
            # پاکسازی کش
            self.cache.pop(self._cache_key("user", user_id), None)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update user {user_id}: {e}")
            return False
            
    async def get_all_users(self) -> List[Dict]:
        """دریافت همه کاربران"""
        try:
            async with self.connection.execute("SELECT * FROM users") as cursor:
                results = await cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            self.logger.error(f"Failed to get all users: {e}")
            return []
            
    async def get_active_users(self, days: int = 7) -> List[Dict]:
        """دریافت کاربران فعال"""
        try:
            query = """
                SELECT * FROM users 
                WHERE last_seen > datetime('now', ?)
            """
            async with self.connection.execute(query, (f'-{days} days',)) as cursor:
                results = await cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            self.logger.error(f"Failed to get active users: {e}")
            return []
            
    # ============================================================
    # متدهای گروه‌ها
    # ============================================================
    
    async def get_group(self, group_id: int) -> Optional[Dict]:
        """دریافت اطلاعات گروه"""
        cache_key = self._cache_key("group", group_id)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        try:
            async with self.connection.execute(
                "SELECT * FROM groups WHERE id = ?", (group_id,)
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    group_dict = dict(result)
                    self._set_cache(cache_key, group_dict)
                    return group_dict
        except Exception as e:
            self.logger.error(f"Failed to get group {group_id}: {e}")
        return None
        
    async def create_group(self, group_id: int, **kwargs) -> bool:
        """ایجاد گروه جدید"""
        try:
            query = """
                INSERT INTO groups (id, title, username, member_count)
                VALUES (?, ?, ?, ?)
            """
            
            await self.connection.execute(
                query,
                (
                    group_id,
                    kwargs.get("title", ""),
                    kwargs.get("username", ""),
                    kwargs.get("member_count", 0)
                )
            )
            
            await self.connection.commit()
            self.cache.pop(self._cache_key("group", group_id), None)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create group {group_id}: {e}")
            return False
            
    # ============================================================
    # متدهای تنظیمات
    # ============================================================
    
    async def get_setting(self, key: str, default: Any = None) -> Any:
        """دریافت یک تنظیم"""
        try:
            async with self.connection.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    try:
                        return json.loads(result[0])
                    except:
                        return result[0]
        except Exception as e:
            self.logger.error(f"Failed to get setting {key}: {e}")
        return default
        
    async def set_setting(self, key: str, value: Any) -> bool:
        """ذخیره یک تنظیم"""
        try:
            value_str = json.dumps(value) if not isinstance(value, str) else value
            
            query = """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
            """
            
            await self.connection.execute(query, (key, value_str, value_str))
            await self.connection.commit()
            
            self.cache.pop(self._cache_key("setting", key), None)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set setting {key}: {e}")
            return False
            
    # ============================================================
    # متدهای پاسخ خودکار
    # ============================================================
    
    async def add_auto_reply(self, keyword: str, response: str) -> bool:
        """افزودن پاسخ خودکار جدید"""
        try:
            await self.connection.execute(
                "INSERT INTO auto_replies (keyword, response) VALUES (?, ?)",
                (keyword, response)
            )
            await self.connection.commit()
            self.cache.pop(self._cache_key("auto_replies"), None)
            return True
        except Exception as e:
            self.logger.error(f"Failed to add auto reply: {e}")
            return False
            
    async def get_auto_reply(self, keyword: str) -> Optional[str]:
        """دریافت پاسخ خودکار برای کلمه کلیدی"""
        cache_key = self._cache_key("auto_reply", keyword)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        try:
            async with self.connection.execute(
                "SELECT response FROM auto_replies WHERE keyword = ? AND is_active = 1",
                (keyword,)
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    self._set_cache(cache_key, result[0])
                    return result[0]
        except Exception as e:
            self.logger.error(f"Failed to get auto reply: {e}")
        return None
        
    async def get_all_auto_replies(self) -> List[Dict]:
        """دریافت همه پاسخ‌های خودکار"""
        cache_key = self._cache_key("auto_replies")
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        try:
            async with self.connection.execute(
                "SELECT * FROM auto_replies WHERE is_active = 1"
            ) as cursor:
                results = await cursor.fetchall()
                replies = [dict(row) for row in results]
                self._set_cache(cache_key, replies)
                return replies
        except Exception as e:
            self.logger.error(f"Failed to get auto replies: {e}")
            return []
            
    # ============================================================
    # متدهای آمار
    # ============================================================
    
    async def _update_daily_stats(self, stat_type: str, value: int = 1):
        """به‌روزرسانی آمار روزانه"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            query = f"""
                INSERT INTO daily_stats (date, {stat_type})
                VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET {stat_type} = {stat_type} + ?
            """
            
            await self.connection.execute(query, (today, value, value))
            await self.connection.commit()
            
            self.cache.pop(self._cache_key("daily_stats"), None)
            
        except Exception as e:
            self.logger.error(f"Failed to update daily stats: {e}")
            
    async def get_daily_stats(self, date: Optional[str] = None) -> Dict:
        """دریافت آمار روزانه"""
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
            
        try:
            async with self.connection.execute(
                "SELECT * FROM daily_stats WHERE date = ?",
                (date,)
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    return dict(result)
        except Exception as e:
            self.logger.error(f"Failed to get daily stats: {e}")
            
        return {
            "date": date,
            "messages_sent": 0,
            "messages_received": 0,
            "commands_used": 0,
            "new_users": 0,
            "active_users": 0
        }
        
    async def get_total_stats(self) -> Dict:
        """دریافت آمار کلی"""
        try:
            total_users = await self.connection.execute("SELECT COUNT(*) FROM users")
            total_groups = await self.connection.execute("SELECT COUNT(*) FROM groups")
            total_messages = await self.connection.execute("SELECT COUNT(*) FROM messages")
            
            total_users = (await total_users.fetchone())[0]
            total_groups = (await total_groups.fetchone())[0]
            total_messages = (await total_messages.fetchone())[0]
            
            return {
                "total_users": total_users,
                "total_groups": total_groups,
                "total_messages": total_messages
            }
        except Exception as e:
            self.logger.error(f"Failed to get total stats: {e}")
            return {"total_users": 0, "total_groups": 0, "total_messages": 0}
            
    # ============================================================
    # متدهای رمزنگاری
    # ============================================================
    
    async def encrypt_data(self, data: str) -> str:
        """رمزنگاری داده"""
        if not self.cipher:
            return data
            
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            self.logger.error(f"Encryption failed: {e}")
            return data
            
    async def decrypt_data(self, encrypted_data: str) -> str:
        """رمزگشایی داده"""
        if not self.cipher:
            return encrypted_data
            
        try:
            decrypted = self.cipher.decrypt(base64.b64decode(encrypted_data))
            return decrypted.decode()
        except Exception as e:
            self.logger.error(f"Decryption failed: {e}")
            return encrypted_data
            
    # ============================================================
    # متدهای عمومی
    # ============================================================
    
    async def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """اجرای کوئری دلخواه"""
        try:
            async with self.connection.execute(query, params) as cursor:
                results = await cursor.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            return []
            
    async def clear_cache(self):
        """پاکسازی کامل کش"""
        self.cache.clear()
        self.logger.info("✅ Cache cleared")
