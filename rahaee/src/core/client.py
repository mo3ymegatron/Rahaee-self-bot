# src/core/client.py

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineQuery
from pyrogram.handlers import MessageHandler, CallbackQueryHandler, InlineQueryHandler
from typing import Optional, Union, List
import logging

from core.config import Config
from core.database import Database


class RahaeiClient:
    """کلاس مدیریت کلاینت تلگرام"""
    
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.logger = logging.getLogger(__name__)
        self.db = bot.db
        
        # ایجاد کلاینت اصلی
        self.app = Client(
            name="rahaee_session",
            api_id=self.config.API_ID,
            api_hash=self.config.API_HASH,
            device_model="Rahaei Self-Bot",
            system_version="Linux",
            app_version="1.0.0",
            lang_code="fa",
            workdir="data"
        )
        
        # تنظیمات کلاینت
        self.is_running = False
        self.handlers = []
        
    async def start(self):
        """راه‌اندازی کلاینت"""
        try:
            await self.app.start()
            self.is_running = True
            
            # دریافت اطلاعات اکانت
            me = await self.app.get_me()
            self.logger.info(f"✅ Logged in as: {me.first_name} (@{me.username})")
            self.logger.info(f"📱 User ID: {me.id}")
            
            # ثبت هندلرهای عمومی
            self._register_handlers()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start client: {e}")
            return False
            
    async def stop(self):
        """توقف کلاینت"""
        try:
            await self.app.stop()
            self.is_running = False
            self.logger.info("✅ Client stopped successfully")
        except Exception as e:
            self.logger.error(f"❌ Failed to stop client: {e}")
            
    def _register_handlers(self):
        """ثبت هندلرهای عمومی"""
        # هندلر پیام‌های خروجی (دستورات سلف)
        @self.app.on_message(filters.me & filters.command("help", "."))
        async def help_handler(client, message):
            await self.bot.handlers['message'].handle_help(client, message)
            
        @self.app.on_message(filters.me & filters.command("panel", "."))
        async def panel_handler(client, message):
            await self.bot.handlers['message'].handle_panel(client, message)
            
        @self.app.on_message(filters.me & filters.command("ping", "."))
        async def ping_handler(client, message):
            await self.bot.handlers['message'].handle_ping(client, message)
            
        @self.app.on_message(filters.me & filters.command("stats", "."))
        async def stats_handler(client, message):
            await self.bot.handlers['message'].handle_stats(client, message)
            
        @self.app.on_message(filters.me & filters.command("ai", "."))
        async def ai_handler(client, message):
            await self.bot.modules['ai'].handle_chat(client, message)
            
        @self.app.on_message(filters.me & filters.command("backup", "."))
        async def backup_handler(client, message):
            await self.bot.handlers['message'].handle_backup(client, message)
            
        @self.app.on_message(filters.me & filters.command("update", "."))
        async def update_handler(client, message):
            await self.bot.handlers['message'].handle_update(client, message)
            
        # هندلر دکمه‌های شیشه‌ای
        @self.app.on_callback_query()
        async def callback_handler(client, callback_query):
            await self.bot.handlers['callback'].handle(client, callback_query)
            
        # هندلر حالت Inline
        @self.app.on_inline_query()
        async def inline_handler(client, inline_query):
            await self.bot.handlers['inline'].handle(client, inline_query)
            
        # هندلر پیام‌های ورودی (برای AFK، منشی و...)
        @self.app.on_message(filters.incoming & ~filters.me)
        async def incoming_handler(client, message):
            await self.bot.handlers['message'].handle_incoming(client, message)
            
        # هندلر خطاها
        @self.app.on_error()
        async def error_handler(client, update, error):
            await self.bot.handlers['errors'].handle(client, update, error)
            
        self.logger.info("✅ All handlers registered successfully")
        
    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        reply_to_message_id: Optional[int] = None,
        parse_mode: str = "markdown",
        **kwargs
    ) -> Optional[Message]:
        """ارسال پیام با مدیریت خطا"""
        try:
            return await self.app.send_message(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=reply_to_message_id,
                parse_mode=parse_mode,
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            return None
            
    async def edit_message(
        self,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        **kwargs
    ) -> Optional[Message]:
        """ویرایش پیام با مدیریت خطا"""
        try:
            return await self.app.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"Failed to edit message: {e}")
            return None
            
    async def delete_message(
        self,
        chat_id: Union[int, str],
        message_id: int
    ) -> bool:
        """حذف پیام با مدیریت خطا"""
        try:
            await self.app.delete_messages(chat_id, message_id)
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete message: {e}")
            return False
            
    async def reply_message(
        self,
        message: Message,
        text: str,
        **kwargs
    ) -> Optional[Message]:
        """پاسخ به پیام با مدیریت خطا"""
        try:
            return await message.reply_text(text, **kwargs)
        except Exception as e:
            self.logger.error(f"Failed to reply message: {e}")
            return None
            
    async def get_user_info(self, user_id: Union[int, str]):
        """دریافت اطلاعات کاربر"""
        try:
            return await self.app.get_users(user_id)
        except Exception as e:
            self.logger.error(f"Failed to get user info: {e}")
            return None
            
    async def get_chat_info(self, chat_id: Union[int, str]):
        """دریافت اطلاعات گپ"""
        try:
            return await self.app.get_chat(chat_id)
        except Exception as e:
            self.logger.error(f"Failed to get chat info: {e}")
            return None
            
    async def is_admin(self, chat_id: Union[int, str], user_id: int) -> bool:
        """بررسی ادمین بودن کاربر"""
        try:
            member = await self.app.get_chat_member(chat_id, user_id)
            return member.status in ["administrator", "creator"]
        except Exception as e:
            self.logger.error(f"Failed to check admin status: {e}")
            return False
