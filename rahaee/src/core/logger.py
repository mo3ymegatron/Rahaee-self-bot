# src/core/logger.py

import logging
import sys
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional
import colorama
from colorama import Fore, Style

# فعال‌سازی رنگ‌ها در ترمینال
colorama.init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """فرمت‌کننده لاگ با رنگ‌های مختلف برای سطوح مختلف"""
    
    # رنگ‌های هر سطح
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }
    
    def __init__(self, fmt: str = None, datefmt: str = None):
        super().__init__(fmt, datefmt)
        
    def format(self, record: logging.LogRecord) -> str:
        # ذخیره سطح اصلی
        original_levelname = record.levelname
        
        # اعمال رنگ
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{Style.RESET_ALL}"
            
        # فرمت پیام
        result = super().format(record)
        
        # بازگرداندن سطح اصلی
        record.levelname = original_levelname
        
        return result


class EmojiFormatter(logging.Formatter):
    """فرمت‌کننده لاگ با ایموجی برای هر سطح"""
    
    EMOJIS = {
        'DEBUG': '🐛',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '💀',
    }
    
    def __init__(self, fmt: str = None, datefmt: str = None):
        super().__init__(fmt, datefmt)
        
    def format(self, record: logging.LogRecord) -> str:
        # اضافه کردن ایموجی
        emoji = self.EMOJIS.get(record.levelname, '📝')
        record.msg = f"{emoji} {record.msg}"
        
        return super().format(record)


class CustomLogger:
    """کلاس مدیریت لاگ‌گیری پیشرفته"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.loggers = {}
        self.log_dir = Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # تنظیمات اصلی
        self.log_level = logging.INFO
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.date_format = "%Y-%m-%d %H:%M:%S"
        
        # تنظیم لاگر ریشه
        self._setup_root_logger()
        
    def _setup_root_logger(self):
        """تنظیم لاگر ریشه"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # حذف هندلرهای قبلی
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # هندلر کنسول (رنگی)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_formatter = ColoredFormatter(
            f"{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.MAGENTA}%(name)s{Style.RESET_ALL} - %(levelname)s - %(message)s",
            self.date_format
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # هندلر فایل (چرخشی بر اساس حجم)
        file_handler = RotatingFileHandler(
            filename=self.log_dir / "rahaee.log",
            maxBytes=10 * 1024 * 1024,  # 10 مگابایت
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_formatter = logging.Formatter(self.log_format, self.date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # هندلر فایل خطاها
        error_handler = RotatingFileHandler(
            filename=self.log_dir / "errors.log",
            maxBytes=5 * 1024 * 1024,  # 5 مگابایت
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(self.log_format, self.date_format)
        error_handler.setFormatter(error_formatter)
        root_logger.addHandler(error_handler)
        
        # هندلر فایل روزانه
        daily_handler = TimedRotatingFileHandler(
            filename=self.log_dir / "daily.log",
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        daily_handler.setLevel(self.log_level)
        daily_handler.setFormatter(logging.Formatter(self.log_format, self.date_format))
        root_logger.addHandler(daily_handler)
        
        # جلوگیری از انتشار لاگ به کتابخانه‌های خارجی
        for logger_name in ['pyrogram', 'apscheduler', 'urllib3']:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
            
    def get_logger(self, name: str = None, emoji: bool = True) -> logging.Logger:
        """دریافت لاگر برای یک ماژول خاص"""
        if not name:
            name = "rahaee"
            
        if name in self.loggers:
            return self.loggers[name]
            
        logger = logging.getLogger(name)
        
        # اضافه کردن هندلر با ایموجی برای این لاگر
        if emoji:
            emoji_handler = logging.StreamHandler(sys.stdout)
            emoji_handler.setLevel(self.log_level)
            emoji_formatter = EmojiFormatter(
                f"%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                self.date_format
            )
            emoji_handler.setFormatter(emoji_formatter)
            logger.addHandler(emoji_handler)
        
        self.loggers[name] = logger
        return logger
        
    def set_level(self, level: str):
        """تغییر سطح لاگ"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        
        if level.upper() in level_map:
            self.log_level = level_map[level.upper()]
            logging.getLogger().setLevel(self.log_level)
            
    def log_with_context(self, logger: logging.Logger, level: str, message: str, **kwargs):
        """لاگ با اطلاعات اضافی"""
        context = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        full_message = f"{message} [{context}]" if context else message
        
        getattr(logger, level.lower())(full_message)


# ============================================================
# توابع کمکی برای استفاده سریع
# ============================================================

def setup_logger(name: str = "rahaee", level: str = "INFO", emoji: bool = True) -> logging.Logger:
    """تنظیم و دریافت لاگر با تنظیمات پیش‌فرض"""
    logger_instance = CustomLogger()
    logger_instance.set_level(level)
    return logger_instance.get_logger(name, emoji)


def get_logger(name: str = "rahaee") -> logging.Logger:
    """دریافت لاگر موجود"""
    return CustomLogger().get_logger(name)


class LoggerContext:
    """مدیریت زمینه لاگ‌گیری"""
    
    def __init__(self, logger: logging.Logger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
        
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"🔄 Starting {self.operation}...")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type:
            self.logger.error(f"❌ {self.operation} failed after {elapsed:.2f}s: {exc_val}")
        else:
            self.logger.info(f"✅ {self.operation} completed in {elapsed:.2f}s")
            
    async def __aenter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"🔄 Starting {self.operation}...")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type:
            self.logger.error(f"❌ {self.operation} failed after {elapsed:.2f}s: {exc_val}")
        else:
            self.logger.info(f"✅ {self.operation} completed in {elapsed:.2f}s")


# ============================================================
# نمونه استفاده
# ============================================================

if __name__ == "__main__":
    # مثال استفاده
    logger = setup_logger("test", "DEBUG")
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # استفاده از context manager
    with LoggerContext(logger, "test_operation"):
        import time
        time.sleep(0.5)
