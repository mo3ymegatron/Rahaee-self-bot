# src/main.py

import asyncio
import logging
import sys
from pathlib import Path

# اضافه کردن مسیر src به sys.path
sys.path.append(str(Path(__file__).parent))

from core.client import RahaeiClient
from core.config import Config
from core.database import Database
from core.logger import setup_logger
from handlers import register_all_handlers


class Rahaei:
    """کلاس اصلی ربات رهایی"""
    
    def __init__(self):
        self.config = Config()
        self.logger = setup_logger()
        self.db = Database()
        self.client = RahaeiClient(self)
        self.modules = {}
        self.start_time = None
        
    async def load_modules(self):
        """بارگذاری همه ماژول‌ها"""
        from modules.ai import AIModule
        from modules.admin import AdminModule
        from modules.tools import ToolsModule
        from modules.games import GamesModule
        
        self.modules = {
            'ai': AIModule(self),
            'admin': AdminModule(self),
            'tools': ToolsModule(self),
            'games': GamesModule(self)
        }
        
        for name, module in self.modules.items():
            try:
                await module.init()
                self.logger.info(f"✅ Module {name} loaded successfully")
            except Exception as e:
                self.logger.error(f"❌ Failed to load module {name}: {e}")
                
    async def start(self):
        """راه‌اندازی ربات"""
        self.start_time = asyncio.get_event_loop().time()
        
        self.logger.info("🚀 Starting Rahaei Self-Bot v1.0.0")
        self.logger.info("📱 Developer: @UXlor")
        
        # اتصال به دیتابیس
        await self.db.connect()
        
        # بارگذاری ماژول‌ها
        await self.load_modules()
        
        # ثبت هندلرها
        register_all_handlers(self)
        
        # راه‌اندازی کلاینت
        await self.client.start()
        
        self.logger.info("✅ Rahaei is now running!")
        
        # ارسال پیام به اکانت مالک
        try:
            await self.client.send_message(
                self.config.OWNER_ID,
                "🚀 **رهایی با موفقیت روشن شد!**\n\n"
                "📱 توسعه‌دهنده: @UXlor\n"
                "📌 نسخه: 1.0.0\n"
                "⚡ برای مشاهده راهنما از `.help` استفاده کنید."
            )
        except Exception as e:
            self.logger.error(f"Failed to send startup message: {e}")
        
        # نگه داشتن ربات در حالت اجرا
        await asyncio.Event().wait()
        
    async def stop(self):
        """توقف ربات"""
        self.logger.info("🛑 Stopping Rahaei...")
        
        # پاکسازی ماژول‌ها
        for name, module in self.modules.items():
            try:
                await module.cleanup()
                self.logger.info(f"✅ Module {name} cleaned up")
            except Exception as e:
                self.logger.error(f"❌ Failed to cleanup module {name}: {e}")
        
        # بستن دیتابیس
        await self.db.disconnect()
        
        # توقف کلاینت
        await self.client.stop()
        
        self.logger.info("👋 Rahaei stopped successfully!")
        
    def get_uptime(self):
        """دریافت زمان آپ‌تایم"""
        if self.start_time:
            elapsed = asyncio.get_event_loop().time() - self.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            return f"{hours}h {minutes}m {seconds}s"
        return "N/A"


async def main():
    """نقطه ورود اصلی برنامه"""
    bot = Rahaei()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n⚠️ Received interrupt signal")
        await bot.stop()
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
        await bot.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
