# src/core/config.py

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path


@dataclass
class Config:
    """کلاس مدیریت تنظیمات برنامه"""
    
    # ============================================================
    # تنظیمات تلگرام
    # ============================================================
    API_ID: int = int(os.getenv("API_ID", 0))
    API_HASH: str = os.getenv("API_HASH", "")
    BOT_TOKEN: Optional[str] = os.getenv("BOT_TOKEN", None)
    OWNER_ID: int = int(os.getenv("OWNER_ID", 0))
    SESSION_NAME: str = os.getenv("SESSION_NAME", "rahaee_session")
    
    # ============================================================
    # تنظیمات دیتابیس
    # ============================================================
    DB_PATH: str = os.getenv("DB_PATH", "data/database.db")
    DB_TYPE: str = os.getenv("DB_TYPE", "sqlite")  # sqlite, postgres, mysql
    
    # ============================================================
    # تنظیمات هوش مصنوعی
    # ============================================================
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    
    # ============================================================
    # تنظیمات امنیتی
    # ============================================================
    SECRET_KEY: str = os.getenv("SECRET_KEY", "rahaee-secret-key-2026")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    # ============================================================
    # تنظیمات وب پنل
    # ============================================================
    WEB_HOST: str = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT: int = int(os.getenv("WEB_PORT", 5000))
    WEB_DEBUG: bool = os.getenv("WEB_DEBUG", "False").lower() == "true"
    WEB_SECRET_KEY: str = os.getenv("WEB_SECRET_KEY", "rahaee-web-secret")
    
    # ============================================================
    # تنظیمات محدودیت‌ها
    # ============================================================
    MAX_USERS: int = int(os.getenv("MAX_USERS", 100))
    MAX_GROUPS: int = int(os.getenv("MAX_GROUPS", 50))
    MAX_MESSAGE_LENGTH: int = int(os.getenv("MAX_MESSAGE_LENGTH", 4096))
    FLOOD_WAIT_SLEEP: int = int(os.getenv("FLOOD_WAIT_SLEEP", 5))
    
    # ============================================================
    # تنظیمات لاگ‌گیری
    # ============================================================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/rahaee.log")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT", 
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # ============================================================
    # تنظیمات مسیرها
    # ============================================================
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "temp")
    DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "downloads")
    
    # ============================================================
    # تنظیمات API های خارجی
    # ============================================================
    WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "")
    TRANSLATE_API_KEY: str = os.getenv("TRANSLATE_API_KEY", "")
    IMDB_API_KEY: str = os.getenv("IMDB_API_KEY", "")
    
    # ============================================================
    # تنظیمات ربات
    # ============================================================
    BOT_NAME: str = os.getenv("BOT_NAME", "رهایی")
    BOT_VERSION: str = os.getenv("BOT_VERSION", "1.0.0")
    BOT_LANGUAGE: str = os.getenv("BOT_LANGUAGE", "fa")  # fa, en, ar
    
    # ============================================================
    # تنظیمات پیشرفته
    # ============================================================
    AUTO_RESTART: bool = os.getenv("AUTO_RESTART", "True").lower() == "true"
    AUTO_BACKUP: bool = os.getenv("AUTO_BACKUP", "True").lower() == "true"
    BACKUP_INTERVAL: int = int(os.getenv("BACKUP_INTERVAL", 86400))  # 24 ساعت
    
    def __post_init__(self):
        """ایجاد پوشه‌های مورد نیاز"""
        for directory in [self.DATA_DIR, self.LOG_DIR, self.TEMP_DIR, self.DOWNLOAD_DIR]:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load(cls):
        """بارگذاری تنظیمات از فایل .env"""
        load_dotenv()
        return cls()
    
    def get(self, key: str, default=None):
        """دریافت یک تنظیم خاص"""
        return getattr(self, key, default)
    
    def is_owner(self, user_id: int) -> bool:
        """بررسی مالک بودن کاربر"""
        return user_id == self.OWNER_ID
    
    def is_valid(self) -> bool:
        """بررسی اعتبار تنظیمات"""
        if not self.API_ID or not self.API_HASH:
            return False
        if not self.OWNER_ID:
            return False
        return True
