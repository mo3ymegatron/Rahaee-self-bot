# src/handlers/errors.py

import sys
import traceback
import asyncio
from datetime import datetime
from typing import Optional, Union, Type
from pyrogram.errors import RPCError, FloodWait, ChatWriteForbidden, UserNotParticipant
from pyrogram.types import Message, CallbackQuery, InlineQuery

from core.logger import get_logger
from core.database import Database
from core.config import Config


class ErrorHandler:
    """مدیریت مرکزی خطاها با قابلیت بازیابی هوشمند"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger("error_handler")
        self.db = bot.db
        self.config = bot.config
        self.client = bot.client
        
        # آمار خطاها
        self.error_counts = {}
        self.last_error_time = {}
        self.critical_errors = 0
        self.max_critical_errors = 5
        
        # خطاهای قابل بازیابی
        self.recoverable_errors = {
            FloodWait: self._handle_flood_wait,
            ChatWriteForbidden: self._handle_chat_write_forbidden,
            UserNotParticipant: self._handle_user_not_participant,
            RPCError: self._handle_rpc_error,
        }
        
    async def handle(self, client, update: Union[Message, CallbackQuery, InlineQuery], error: Exception):
        """هندلر اصلی خطاها"""
        try:
            # ثبت خطا
            error_type = type(error).__name__
            error_msg = str(error)
            
            # افزایش شمارنده خطا
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
            self.last_error_time[error_type] = datetime.now()
            
            # لاگ خطا
            self.logger.error(
                f"❌ Error: {error_type} | {error_msg}\n"
                f"📱 Update: {type(update).__name__}\n"
                f"🔍 Traceback:\n{traceback.format_exc()}"
            )
            
            # ذخیره در دیتابیس (اگر خطا بحرانی نباشد)
            if not self._is_critical_error(error):
                await self._save_error_log(error_type, error_msg, traceback.format_exc())
            
            # افزایش خطاهای بحرانی
            if self._is_critical_error(error):
                self.critical_errors += 1
                if self.critical_errors >= self.max_critical_errors:
                    await self._handle_critical_error()
            
            # پردازش خطا بر اساس نوع
            if type(error) in self.recoverable_errors:
                await self.recoverable_errors[type(error)](update, error)
            else:
                await self._handle_generic_error(update, error)
                
        except Exception as e:
            # خطا در هندلر خطا! 🤯
            self.logger.critical(f"💀 Error in error handler: {e}")
            self.logger.critical(traceback.format_exc())
            
    # ============================================================
    # تشخیص انواع خطا
    # ============================================================
    
    def _is_critical_error(self, error: Exception) -> bool:
        """بررسی بحرانی بودن خطا"""
        critical_types = (
            MemoryError,
            SystemError,
            KeyboardInterrupt,
            SystemExit,
            ConnectionError,
            TimeoutError,
        )
        return isinstance(error, critical_types)
        
    def _is_user_error(self, error: Exception) -> bool:
        """بررسی خطای کاربر (غیر بحرانی)"""
        user_error_types = (
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            ChatWriteForbidden,
            UserNotParticipant,
        )
        return isinstance(error, user_error_types)
        
    # ============================================================
    # هندلرهای خطاهای خاص
    # ============================================================
    
    async def _handle_flood_wait(self, update: Union[Message, CallbackQuery, InlineQuery], error: FloodWait):
        """مدیریت خطای FloodWait"""
        wait_time = error.x if hasattr(error, 'x') else 5
        self.logger.warning(f"⏳ FloodWait: {wait_time} seconds")
        
        # اطلاع به کاربر
        if isinstance(update, Message):
            try:
                await update.reply_text(
                    f"⏳ **لطفاً صبر کنید...**\n"
                    f"تلگرام محدودیت سرعت اعمال کرده است.\n"
                    f"زمان انتظار: `{wait_time}` ثانیه"
                )
            except:
                pass
                
        # انتظار
        await asyncio.sleep(wait_time + 1)
        
    async def _handle_chat_write_forbidden(self, update: Union[Message, CallbackQuery, InlineQuery], error: ChatWriteForbidden):
        """مدیریت خطای عدم دسترسی به نوشتن در چت"""
        chat_id = None
        if isinstance(update, Message):
            chat_id = update.chat.id
        elif hasattr(update, 'message'):
            chat_id = update.message.chat.id
            
        self.logger.warning(f"🚫 Chat write forbidden: {chat_id}")
        
        # اطلاع به کاربر
        if isinstance(update, Message) and update.from_user:
            try:
                await self.client.send_message(
                    update.from_user.id,
                    f"🚫 **دسترسی به نوشتن در چت وجود ندارد!**\n"
                    f"لطفاً ربات را به عنوان ادمین در گروه اضافه کنید."
                )
            except:
                pass
                
    async def _handle_user_not_participant(self, update: Union[Message, CallbackQuery, InlineQuery], error: UserNotParticipant):
        """مدیریت خطای عدم عضویت کاربر"""
        self.logger.warning("👤 User not participant")
        
        if isinstance(update, Message):
            try:
                await update.reply_text(
                    "🔒 **برای استفاده از این قابلیت، باید عضو کانال/گروه باشید.**"
                )
            except:
                pass
                
    async def _handle_rpc_error(self, update: Union[Message, CallbackQuery, InlineQuery], error: RPCError):
        """مدیریت خطاهای RPC"""
        error_message = str(error)
        
        # خطاهای رایج RPC
        if "USER_ID_INVALID" in error_message:
            await self._handle_user_id_invalid(update)
        elif "PEER_ID_INVALID" in error_message:
            await self._handle_peer_id_invalid(update)
        elif "MESSAGE_ID_INVALID" in error_message:
            await self._handle_message_id_invalid(update)
        elif "CHAT_ADMIN_REQUIRED" in error_message:
            await self._handle_chat_admin_required(update)
        elif "CHAT_SEND_MEDIA_FORBIDDEN" in error_message:
            await self._handle_send_media_forbidden(update)
        else:
            await self._handle_generic_rpc_error(update, error)
            
    # ============================================================
    # هندلرهای خطاهای RPC خاص
    # ============================================================
    
    async def _handle_user_id_invalid(self, update: Union[Message, CallbackQuery, InlineQuery]):
        """مدیریت خطای کاربر نامعتبر"""
        if isinstance(update, Message):
            await update.reply_text(
                "❌ **آیدی کاربر نامعتبر است!**\n"
                "لطفاً آیدی صحیح را وارد کنید."
            )
            
    async def _handle_peer_id_invalid(self, update: Union[Message, CallbackQuery, InlineQuery]):
        """مدیریت خطای چت نامعتبر"""
        if isinstance(update, Message):
            await update.reply_text(
                "❌ **چت نامعتبر است!**\n"
                "لطفاً از یک چت معتبر استفاده کنید."
            )
            
    async def _handle_message_id_invalid(self, update: Union[Message, CallbackQuery, InlineQuery]):
        """مدیریت خطای پیام نامعتبر"""
        if isinstance(update, Message):
            await update.reply_text(
                "❌ **پیام نامعتبر است!**\n"
                "ممکن است پیام حذف شده باشد."
            )
            
    async def _handle_chat_admin_required(self, update: Union[Message, CallbackQuery, InlineQuery]):
        """مدیریت خطای نیاز به ادمین"""
        if isinstance(update, Message):
            await update.reply_text(
                "👮 **نیاز به دسترسی ادمین دارید!**\n"
                "لطفاً ربات را به عنوان ادمین در گروه اضافه کنید."
            )
            
    async def _handle_send_media_forbidden(self, update: Union[Message, CallbackQuery, InlineQuery]):
        """مدیریت خطای ارسال مدیا ممنوع"""
        if isinstance(update, Message):
            await update.reply_text(
                "🚫 **ارسال مدیا در این چت ممنوع است!**\n"
                "لطفاً از متن استفاده کنید."
            )
            
    async def _handle_generic_rpc_error(self, update: Union[Message, CallbackQuery, InlineQuery], error: RPCError):
        """مدیریت خطاهای RPC عمومی"""
        error_msg = str(error)
        
        if isinstance(update, Message):
            try:
                await update.reply_text(
                    f"❌ **خطا در ارتباط با تلگرام:**\n"
                    f"```\n{error_msg[:200]}\n```"
                )
            except:
                pass
                
    # ============================================================
    # هندلرهای خطاهای عمومی
    # ============================================================
    
    async def _handle_generic_error(self, update: Union[Message, CallbackQuery, InlineQuery], error: Exception):
        """مدیریت خطاهای عمومی"""
        error_msg = str(error)
        
        # پیام مناسب برای کاربر
        user_message = self._get_user_friendly_message(error)
        
        # ارسال به کاربر
        if isinstance(update, Message):
            try:
                await update.reply_text(user_message)
            except:
                pass
        elif isinstance(update, CallbackQuery):
            try:
                await update.answer(f"❌ {error_msg[:50]}", show_alert=True)
            except:
                pass
                
        # اگر خطا بحرانی است، به مالک اطلاع بده
        if self._is_critical_error(error):
            await self._notify_owner(error)
            
    async def _handle_critical_error(self):
        """مدیریت خطاهای بحرانی"""
        self.logger.critical(f"💀 Critical error limit reached: {self.critical_errors}")
        
        # ریستارت کردن ربات
        await self._restart_bot()
        
    # ============================================================
    # توابع کمکی
    # ============================================================
    
    def _get_user_friendly_message(self, error: Exception) -> str:
        """دریافت پیام کاربرپسند برای خطا"""
        error_type = type(error).__name__
        
        messages = {
            "ValueError": "❌ **مقدار نامعتبر!**\nلطفاً مقدار صحیح را وارد کنید.",
            "TypeError": "❌ **نوع داده نامعتبر!**\nلطفاً نوع داده صحیح را وارد کنید.",
            "AttributeError": "❌ **خطا در دسترسی به ویژگی!**",
            "KeyError": "❌ **کلید مورد نظر یافت نشد!**",
            "IndexError": "❌ **شاخص نامعتبر!**",
            "TimeoutError": "⏰ **زمان پاسخگویی تمام شد!**\nلطفاً دوباره تلاش کنید.",
            "ConnectionError": "🔌 **مشکل در اتصال به اینترنت!**\nلطفاً اتصال خود را بررسی کنید.",
            "MemoryError": "💾 **حافظه کافی نیست!**\nلطفاً برنامه را ریستارت کنید.",
            "FileNotFoundError": "📁 **فایل مورد نظر یافت نشد!**",
            "PermissionError": "🔒 **دسترسی کافی ندارید!**",
        }
        
        return messages.get(error_type, f"❌ **خطا:** `{str(error)[:100]}`")
        
    async def _save_error_log(self, error_type: str, error_msg: str, traceback_text: str):
        """ذخیره لاگ خطا در دیتابیس"""
        try:
            await self.db.execute_query(
                "INSERT INTO logs (level, module, message) VALUES (?, ?, ?)",
                ("ERROR", f"error_handler.{error_type}", f"{error_msg}\n{traceback_text[:500]}")
            )
        except:
            pass
            
    async def _notify_owner(self, error: Exception):
        """اطلاع به مالک در مورد خطای بحرانی"""
        try:
            error_type = type(error).__name__
            error_msg = str(error)
            
            await self.client.send_message(
                self.config.OWNER_ID,
                f"💀 **خطای بحرانی در رهایی!**\n"
                f"━━━━━━━━━━━━━\n"
                f"🔍 **نوع:** `{error_type}`\n"
                f"📝 **پیام:** `{error_msg[:200]}`\n"
                f"⏰ **زمان:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"━━━━━━━━━━━━━\n"
                f"🔄 ربات در حال ریستارت است..."
            )
        except:
            pass
            
    async def _restart_bot(self):
        """ریستارت کردن ربات"""
        self.logger.info("🔄 Restarting bot...")
        await self.bot.stop()
        
        # اجرای مجدد
        import os
        import sys
        os.execv(sys.executable, [sys.executable] + sys.argv)
        
    # ============================================================
    # دکوریتور برای هندلینگ خودکار خطا
    # ============================================================
    
    @staticmethod
    def catch_errors(func):
        """دکوریتور برای گرفتن خودکار خطاها"""
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except Exception as e:
                # استفاده از ErrorHandler
                error_handler = self.bot.handlers.get('errors')
                if error_handler:
                    # پیدا کردن update از args
                    update = args[0] if args else None
                    await error_handler.handle(self.bot.client, update, e)
                else:
                    # فال‌بک
                    self.logger.error(f"Unhandled error: {e}")
                    raise
        return wrapper
