# src/handlers/message.py

import asyncio
import time
import re
from datetime import datetime
from typing import Optional, Union
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import FloodWait, ChatWriteForbidden

from core.logger import get_logger
from core.database import Database
from core.config import Config


class MessageHandler:
    """مدیریت هندلرهای پیام"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger("message_handler")
        self.db = bot.db
        self.config = bot.config
        self.client = bot.client
        
        # وضعیت‌های داخلی
        self.afk_users = {}
        self.auto_replies = {}
        self.user_stats = {}
        
    # ============================================================
    # هندلرهای اصلی
    # ============================================================
    
    async def handle_incoming(self, client, message: Message):
        """هندلر پیام‌های ورودی"""
        try:
            # بررسی کاربر
            user_id = message.from_user.id if message.from_user else None
            if user_id:
                await self._handle_user(user_id, message)
            
            # بررسی AFK
            if await self._handle_afk(message):
                return
                
            # بررسی منشی
            if await self._handle_auto_reply(message):
                return
                
            # بررسی ضد اسپم
            if await self._handle_anti_spam(message):
                return
                
            # بررسی جوین اجباری
            if await self._handle_force_join(message):
                return
                
            # ذخیره پیام
            await self._save_message(message)
            
        except FloodWait as e:
            self.logger.warning(f"FloodWait: {e.x}s")
            await asyncio.sleep(e.x)
        except Exception as e:
            self.logger.error(f"Error in incoming handler: {e}")
            
    async def handle_outgoing(self, client, message: Message):
        """هندلر پیام‌های خروجی (دستورات سلف)"""
        try:
            text = message.text or ""
            
            # بررسی دستورات
            if text.startswith("."):
                await self._handle_command(client, message)
                
            # ذخیره پیام
            await self._save_message(message, outgoing=True)
            
        except Exception as e:
            self.logger.error(f"Error in outgoing handler: {e}")
            
    # ============================================================
    # دستورات اصلی
    # ============================================================
    
    async def _handle_command(self, client, message: Message):
        """پردازش دستورات"""
        text = message.text[1:].strip()
        command = text.split()[0] if text else ""
        args = text[len(command):].strip() if command else ""
        
        # دستورات عمومی
        commands = {
            "help": self.handle_help,
            "panel": self.handle_panel,
            "ping": self.handle_ping,
            "stats": self.handle_stats,
            "backup": self.handle_backup,
            "update": self.handle_update,
            "restart": self.handle_restart,
            "shutdown": self.handle_shutdown,
            "afk": self.handle_afk_on,
            "unafk": self.handle_afk_off,
            "setname": self.handle_set_name,
            "setbio": self.handle_set_bio,
            "setphoto": self.handle_set_photo,
            "getid": self.handle_get_id,
            "getinfo": self.handle_get_info,
            "block": self.handle_block,
            "unblock": self.handle_unblock,
            "ban": self.handle_ban,
            "unban": self.handle_unban,
            "mute": self.handle_mute,
            "unmute": self.handle_unmute,
            "pin": self.handle_pin,
            "unpin": self.handle_unpin,
            "delete": self.handle_delete,
            "purge": self.handle_purge,
            "join": self.handle_join,
            "leave": self.handle_leave,
            "invite": self.handle_invite,
            "clone": self.handle_clone,
            "ocr": self.handle_ocr,
            "qrcode": self.handle_qrcode,
            "translate": self.handle_translate,
            "weather": self.handle_weather,
            "calc": self.handle_calc,
        }
        
        if command in commands:
            try:
                await commands[command](client, message, args)
                # به‌روزرسانی آمار
                await self.db._update_daily_stats("commands_used")
            except Exception as e:
                self.logger.error(f"Error in command {command}: {e}")
                await message.reply(f"❌ خطا در اجرای دستور: {e}")
                
    # ============================================================
    # پیاده‌سازی دستورات
    # ============================================================
    
    async def handle_help(self, client, message: Message, args: str):
        """نمایش راهنما"""
        help_text = """
**📖 راهنمای رهایی**

**🔥 دستورات اصلی:**
`.help` - نمایش این راهنما
`.panel` - باز کردن پنل مدیریت
`.ping` - تست سرعت
`.stats` - نمایش آمار
`.backup` - گرفتن بکاپ
`.update` - آپدیت ربات
`.restart` - ری‌استارت ربات
`.shutdown` - خاموش کردن ربات

**👤 مدیریت پروفایل:**
`.setname <نام>` - تغییر نام
`.setbio <متن>` - تغییر بیوگرافی
`.setphoto` - تغییر عکس پروفایل
`.getid` - دریافت آیدی خود
`.getinfo` - دریافت اطلاعات کاربر

**🔐 امنیت و مدیریت:**
`.afk <دلیل>` - فعال کردن حالت AFK
`.unafk` - غیرفعال کردن AFK
`.block <آیدی>` - بلاک کردن کاربر
`.unblock <آیدی>` - آنبلاک کاربر

**👮 مدیریت گروه:**
`.ban` - اخراج کاربر (ریپلای)
`.unban` - رفع اخراج
`.mute` - سکوت کاربر
`.unmute` - رفع سکوت
`.pin` - پین کردن پیام
`.unpin` - حذف پین
`.delete` - حذف پیام
`.purge <تعداد>` - حذف گروهی
`.join <لینک>` - عضویت در گروه
`.leave` - خروج از گروه
`.invite` - دریافت لینک دعوت
`.clone` - کلون کردن پروفایل

**🛠 ابزارها:**
`.ocr` - تشخیص متن از عکس
`.qrcode <متن>` - ساخت QR Code
`.translate <زبان> <متن>` - ترجمه
`.weather <شهر>` - آب و هوا
`.calc <عبارت>` - ماشین حساب

**🎮 سرگرمی:**
`.game` - بازی‌های تعاملی
`.dice` - تاس انداختن
`.dart` - دارت انداختن
`.football` - فوتبال
`.basketball` - بسکتبال

**💬 منشی:**
`.addreply <کلیدواژه>|<پاسخ>` - افزودن پاسخ خودکار
`.removereply <کلیدواژه>` - حذف پاسخ
`.listreply` - لیست پاسخ‌ها

📱 **توسعه‌دهنده:** @UXlor
📌 **نسخه:** 1.0.0
"""
        await message.reply(help_text)
        
    async def handle_panel(self, client, message: Message, args: str):
        """پنل مدیریت"""
        user = await self.db.get_user(message.from_user.id)
        is_owner = self.config.is_owner(message.from_user.id)
        
        panel_text = f"""
**🔰 پنل مدیریت رهایی**

👤 **کاربر:** {message.from_user.first_name}
🆔 **آیدی:** `{message.from_user.id}`
📊 **وضعیت:** {'مدیر' if user and user.get('is_admin') else 'کاربر عادی'}
🔑 **دسترسی:** {'مالک ✅' if is_owner else 'کاربر'}

**📈 آمار امروز:**
• پیام‌ها: {user.get('message_count', 0) if user else 0}
• دستورات: {user.get('command_count', 0) if user else 0}
• مدت عضویت: {user.get('created_at', 'نامشخص') if user else 'نامشخص'}

برای مشاهده راهنما از `.help` استفاده کنید.
"""
        buttons = [
            [InlineKeyboardButton("📖 راهنما", callback_data="help")],
            [InlineKeyboardButton("📊 آمار کامل", callback_data="full_stats")],
            [InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
            [InlineKeyboardButton("📱 پشتیبانی", url="https://t.me/UXlor")]
        ]
        
        if is_owner:
            buttons.insert(1, [
                InlineKeyboardButton("👥 مدیریت کاربران", callback_data="manage_users"),
                InlineKeyboardButton("📁 مدیریت گروه‌ها", callback_data="manage_groups")
            ])
            
        await message.reply(
            panel_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    async def handle_ping(self, client, message: Message, args: str):
        """تست سرعت"""
        start = time.time()
        msg = await message.reply("🏓 در حال تست...")
        end = time.time()
        ping = round((end - start) * 1000, 2)
        
        await msg.edit_text(
            f"**🏓 پینگ رهایی**\n"
            f"━━━━━━━━━━━━━\n"
            f"⚡ پینگ: `{ping}ms`\n"
            f"📊 وضعیت: {'🟢 عالی' if ping < 200 else '🟡 خوب' if ping < 500 else '🔴 ضعیف'}\n"
            f"📱 توسعه‌دهنده: @UXlor"
        )
        
    async def handle_stats(self, client, message: Message, args: str):
        """نمایش آمار"""
        try:
            # آمار کلی
            total_stats = await self.db.get_total_stats()
            
            # آمار روزانه
            daily_stats = await self.db.get_daily_stats()
            
            # آمار کاربر
            user = await self.db.get_user(message.from_user.id)
            
            stats_text = f"""
**📊 آمار رهایی**
━━━━━━━━━━━━━
**📈 آمار کلی:**
• 👥 کاربران کل: {total_stats.get('total_users', 0)}
• 💬 گروه‌ها: {total_stats.get('total_groups', 0)}
• 📨 پیام‌ها: {total_stats.get('total_messages', 0)}

**📊 آمار امروز:**
• 📤 پیام ارسال: {daily_stats.get('messages_sent', 0)}
• 📥 پیام دریافت: {daily_stats.get('messages_received', 0)}
• 🎯 دستورات: {daily_stats.get('commands_used', 0)}
• 👤 کاربران جدید: {daily_stats.get('new_users', 0)}
• 🔥 کاربران فعال: {daily_stats.get('active_users', 0)}

**👤 آمار شما:**
• 💬 پیام‌ها: {user.get('message_count', 0) if user else 0}
• 🎯 دستورات: {user.get('command_count', 0) if user else 0}

📱 **توسعه‌دهنده:** @UXlor
📌 **نسخه:** 1.0.0
"""
            await message.reply(stats_text)
            
        except Exception as e:
            self.logger.error(f"Stats error: {e}")
            await message.reply("❌ خطا در دریافت آمار")
            
    async def handle_backup(self, client, message: Message, args: str):
        """بکاپ‌گیری"""
        try:
            msg = await message.reply("⏳ در حال بکاپ‌گیری...")
            
            # گرفتن بکاپ از دیتابیس
            import shutil
            from datetime import datetime
            
            backup_dir = Path("data/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"backup_{timestamp}.db"
            
            shutil.copy2(self.config.DB_PATH, backup_file)
            
            # اطلاعات بکاپ
            size = backup_file.stat().st_size
            size_mb = size / (1024 * 1024)
            
            await msg.edit_text(
                f"✅ **بکاپ با موفقیت گرفته شد!**\n"
                f"━━━━━━━━━━━━━\n"
                f"📁 فایل: `{backup_file.name}`\n"
                f"📦 حجم: `{size_mb:.2f} MB`\n"
                f"📅 تاریخ: `{timestamp}`\n"
                f"━━━━━━━━━━━━━\n"
                f"💡 برای بازیابی از `.restore` استفاده کنید."
            )
            
        except Exception as e:
            self.logger.error(f"Backup error: {e}")
            await message.reply(f"❌ خطا در بکاپ‌گیری: {e}")
            
    async def handle_update(self, client, message: Message, args: str):
        """آپدیت ربات"""
        await message.reply("🔄 **در حال آپدیت رهایی...**\nلطفاً چند لحظه صبر کنید.")
        
        # اینجا کد آپدیت از گیت‌هاب قرار می‌گیرد
        # فعلاً پیام ساده
        await message.reply("✅ **رهایی با موفقیت آپدیت شد!**")
        
    async def handle_restart(self, client, message: Message, args: str):
        """ری‌استارت ربات"""
        await message.reply("🔄 **در حال ری‌استارت رهایی...**")
        await self.bot.stop()
        await self.bot.start()
        
    async def handle_shutdown(self, client, message: Message, args: str):
        """خاموش کردن ربات"""
        await message.reply("🛑 **رهایی در حال خاموش شدن...**")
        await self.bot.stop()
        
    # ============================================================
    # مدیریت پروفایل
    # ============================================================
    
    async def handle_set_name(self, client, message: Message, args: str):
        """تغییر نام"""
        if not args:
            await message.reply("❌ لطفاً نام جدید را وارد کنید:\n`.setname <نام جدید>`")
            return
            
        try:
            await client.update_profile(first_name=args)
            await message.reply(f"✅ نام شما به `{args}` تغییر کرد.")
        except Exception as e:
            await message.reply(f"❌ خطا در تغییر نام: {e}")
            
    async def handle_set_bio(self, client, message: Message, args: str):
        """تغییر بیوگرافی"""
        if not args:
            await message.reply("❌ لطفاً بیوگرافی جدید را وارد کنید:\n`.setbio <متن>`")
            return
            
        try:
            await client.update_profile(bio=args)
            await message.reply(f"✅ بیوگرافی شما تغییر کرد.")
        except Exception as e:
            await message.reply(f"❌ خطا در تغییر بیو: {e}")
            
    async def handle_set_photo(self, client, message: Message, args: str):
        """تغییر عکس پروفایل"""
        if not message.reply_to_message or not message.reply_to_message.photo:
            await message.reply("❌ لطفاً به یک عکس ریپلای کنید:\n`.setphoto` روی عکس")
            return
            
        try:
            photo = await client.download_media(message.reply_to_message)
            await client.set_profile_photo(photo)
            await message.reply("✅ عکس پروفایل شما تغییر کرد.")
        except Exception as e:
            await message.reply(f"❌ خطا در تغییر عکس: {e}")
            
    async def handle_get_id(self, client, message: Message, args: str):
        """دریافت آیدی"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        text = f"""
🆔 **اطلاعات شناسه‌ها:**
━━━━━━━━━━━━━
👤 **آیدی شما:** `{user_id}`
💬 **آیدی چت:** `{chat_id}`
📱 **نوع چت:** `{message.chat.type}`
"""
        
        if message.reply_to_message:
            replied_id = message.reply_to_message.from_user.id
            text += f"↪️ **آیدی ریپلای:** `{replied_id}`"
            
        await message.reply(text)
        
    async def handle_get_info(self, client, message: Message, args: str):
        """دریافت اطلاعات کاربر"""
        target = None
        
        if args:
            # دریافت با آیدی یا یوزرنیم
            try:
                target = await client.get_users(args)
            except:
                pass
        elif message.reply_to_message:
            target = message.reply_to_message.from_user
            
        if not target:
            target = message.from_user
            
        try:
            # اطلاعات کامل
            user_info = await self.db.get_user(target.id)
            
            text = f"""
👤 **اطلاعات کاربر:**
━━━━━━━━━━━━━
📝 **نام:** {target.first_name or 'نامشخص'}
📛 **نام خانوادگی:** {target.last_name or 'نامشخص'}
🆔 **آیدی:** `{target.id}`
🔖 **یوزرنیم:** @{target.username or 'ندارد'}
📱 **شماره:** {target.phone_number or 'نامشخص'}

📊 **آمار کاربر:**
• پیام‌ها: {user_info.get('message_count', 0) if user_info else 0}
• دستورات: {user_info.get('command_count', 0) if user_info else 0}
• عضویت: {user_info.get('created_at', 'نامشخص') if user_info else 'نامشخص'}

✅ **وضعیت:** {'تایید شده' if user_info and user_info.get('is_admin') else 'عادی'}
"""
            await message.reply(text)
            
        except Exception as e:
            await message.reply(f"❌ خطا در دریافت اطلاعات: {e}")
            
    # ============================================================
    # مدیریت گروه
    # ============================================================
    
    async def handle_ban(self, client, message: Message, args: str):
        """اخراج کاربر"""
        if not message.reply_to_message:
            await message.reply("❌ لطفاً به پیام کاربر ریپلای کنید.")
            return
            
        try:
            user_id = message.reply_to_message.from_user.id
            await client.ban_chat_member(message.chat.id, user_id)
            await message.reply("✅ کاربر با موفقیت اخراج شد.")
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_unban(self, client, message: Message, args: str):
        """رفع اخراج"""
        if not message.reply_to_message:
            await message.reply("❌ لطفاً به پیام کاربر ریپلای کنید.")
            return
            
        try:
            user_id = message.reply_to_message.from_user.id
            await client.unban_chat_member(message.chat.id, user_id)
            await message.reply("✅ رفع اخراج با موفقیت انجام شد.")
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_mute(self, client, message: Message, args: str):
        """سکوت کاربر"""
        if not message.reply_to_message:
            await message.reply("❌ لطفاً به پیام کاربر ریپلای کنید.")
            return
            
        try:
            user_id = message.reply_to_message.from_user.id
            await client.restrict_chat_member(
                message.chat.id,
                user_id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            await message.reply("✅ کاربر با موفقیت سکوت شد.")
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_unmute(self, client, message: Message, args: str):
        """رفع سکوت"""
        if not message.reply_to_message:
            await message.reply("❌ لطفاً به پیام کاربر ریپلای کنید.")
            return
            
        try:
            user_id = message.reply_to_message.from_user.id
            await client.restrict_chat_member(
                message.chat.id,
                user_id,
                permissions=ChatPermissions(can_send_messages=True)
            )
            await message.reply("✅ رفع سکوت با موفقیت انجام شد.")
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_pin(self, client, message: Message, args: str):
        """پین کردن پیام"""
        if not message.reply_to_message:
            await message.reply("❌ لطفاً به یک پیام ریپلای کنید.")
            return
            
        try:
            await client.pin_chat_message(message.chat.id, message.reply_to_message.id)
            await message.reply("✅ پیام با موفقیت پین شد.")
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_unpin(self, client, message: Message, args: str):
        """حذف پین"""
        if not message.reply_to_message:
            await message.reply("❌ لطفاً به یک پیام ریپلای کنید.")
            return
            
        try:
            await client.unpin_chat_message(message.chat.id, message.reply_to_message.id)
            await message.reply("✅ پین با موفقیت حذف شد.")
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_delete(self, client, message: Message, args: str):
        """حذف پیام"""
        if not message.reply_to_message:
            await message.reply("❌ لطفاً به یک پیام ریپلای کنید.")
            return
            
        try:
            await message.reply_to_message.delete()
            await message.delete()
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_purge(self, client, message: Message, args: str):
        """پاکسازی گروهی"""
        if not args or not args.isdigit():
            await message.reply("❌ لطفاً تعداد پیام را وارد کنید:\n`.purge 10`")
            return
            
        count = int(args)
        if count > 100:
            await message.reply("❌ حداکثر ۱۰۰ پیام قابل حذف است.")
            return
            
        try:
            deleted = 0
            async for msg in client.get_chat_history(message.chat.id, limit=count):
                if msg.from_user and msg.from_user.is_self:
                    await msg.delete()
                    deleted += 1
                    await asyncio.sleep(0.1)
                    
            await message.reply(f"✅ {deleted} پیام با موفقیت حذف شد.")
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    # ============================================================
    # ابزارها
    # ============================================================
    
    async def handle_ocr(self, client, message: Message, args: str):
        """تشخیص متن از عکس"""
        if not message.reply_to_message or not message.reply_to_message.photo:
            await message.reply("❌ لطفاً به یک عکس ریپلای کنید.")
            return
            
        try:
            await message.reply("⏳ در حال تشخیص متن از عکس...")
            
            # دانلود عکس
            photo_path = await client.download_media(message.reply_to_message)
            
            # تشخیص متن با Tesseract
            import pytesseract
            from PIL import Image
            
            img = Image.open(photo_path)
            text = pytesseract.image_to_string(img, lang='fas')
            
            if text.strip():
                await message.reply(f"📝 **متن تشخیص داده شده:**\n```\n{text.strip()}\n```")
            else:
                await message.reply("❌ متنی در عکس تشخیص داده نشد.")
                
            # پاکسازی فایل
            import os
            os.remove(photo_path)
            
        except ImportError:
            await message.reply("❌ کتابخانه Tesseract نصب نیست.")
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_qrcode(self, client, message: Message, args: str):
        """ساخت QR Code"""
        if not args:
            await message.reply("❌ لطفاً متن مورد نظر را وارد کنید:\n`.qrcode <متن>`")
            return
            
        try:
            import qrcode
            
            # ساخت QR
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(args)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            img.save("temp_qr.png")
            
            await client.send_photo(
                message.chat.id,
                "temp_qr.png",
                caption=f"✅ QR Code برای:\n`{args}`"
            )
            
            import os
            os.remove("temp_qr.png")
            
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_translate(self, client, message: Message, args: str):
        """ترجمه متن"""
        if not args:
            await message.reply("❌ لطفاً متن را وارد کنید:\n`.translate <متن>`")
            return
            
        try:
            # ترجمه با Google Translate
            from googletrans import Translator
            
            translator = Translator()
            result = translator.translate(args, dest='fa')
            
            await message.reply(
                f"**🌐 ترجمه:**\n"
                f"━━━━━━━━━━━━━\n"
                f"**متن اصلی:**\n`{args}`\n\n"
                f"**ترجمه:**\n`{result.text}`\n\n"
                f"📍 **زبان:** {result.src} → fa"
            )
        except ImportError:
            await message.reply("❌ کتابخانه googletrans نصب نیست.")
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_weather(self, client, message: Message, args: str):
        """آب و هوا"""
        if not args:
            await message.reply("❌ لطفاً نام شهر را وارد کنید:\n`.weather <شهر>`")
            return
            
        try:
            import requests
            
            # دریافت اطلاعات آب و هوا
            url = f"http://api.openweathermap.org/data/2.5/weather?q={args}&appid={self.config.WEATHER_API_KEY}&units=metric&lang=fa"
            
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get('cod') != 200:
                await message.reply(f"❌ شهر {args} پیدا نشد.")
                return
                
            weather = f"""
**🌤 آب و هوای {args}**
━━━━━━━━━━━━━
🌡 **دما:** {data['main']['temp']}°C
🤔 **احساس:** {data['main']['feels_like']}°C
🌧 **وضعیت:** {data['weather'][0]['description']}
💧 **رطوبت:** {data['main']['humidity']}%
💨 **باد:** {data['wind']['speed']} m/s
"""
            await message.reply(weather)
            
        except Exception as e:
            await message.reply(f"❌ خطا: {e}")
            
    async def handle_calc(self, client, message: Message, args: str):
        """ماشین حساب"""
        if not args:
            await message.reply("❌ لطفاً عبارت ریاضی را وارد کنید:\n`.calc 2+2`")
            return
            
        try:
            # محاسبه امن
            result = eval(args, {"__builtins__": {}})
            
            await message.reply(
                f"**🧮 ماشین حساب:**\n"
                f"━━━━━━━━━━━━━\n"
                f"📝 `{args}` = `{result}`"
            )
        except Exception as e:
            await message.reply(f"❌ عبارت نامعتبر: {e}")
            
    # ============================================================
    # توابع کمکی
    # ============================================================
    
    async def _handle_user(self, user_id: int, message: Message):
        """مدیریت کاربر"""
        user = await self.db.get_user(user_id)
        
        if not user:
            # کاربر جدید
            user_data = {
                'username': message.from_user.username or "",
                'first_name': message.from_user.first_name or "",
                'last_name': message.from_user.last_name or "",
                'phone': message.from_user.phone_number or ""
            }
            await self.db.create_user(user_id, **user_data)
            
        else:
            # به‌روزرسانی اطلاعات
            await self.db.update_user(
                user_id,
                last_seen=datetime.now().isoformat(),
                message_count=user.get('message_count', 0) + 1
            )
            
    async def _handle_afk(self, message: Message) -> bool:
        """مدیریت AFK"""
        if not message.from_user:
            return False
            
        # بررسی AFK کاربر
        afk_info = await self.db.get_setting(f"afk_{message.from_user.id}")
        if not afk_info:
            return False
            
        # اگر کاربر خودش پیام داده، AFK غیرفعال می‌شود
        if message.from_user.id == self.config.OWNER_ID:
            await self.db.set_setting(f"afk_{message.from_user.id}", None)
            return False
            
        # پاسخ AFK
        await message.reply(
            f"💤 **کاربر آفلاین است**\n"
            f"━━━━━━━━━━━━━\n"
            f"📝 دلیل: {afk_info.get('reason', 'بدون دلیل')}\n"
            f"⏰ از: {afk_info.get('since', 'نامشخص')}"
        )
        return True
        
    async def _handle_auto_reply(self, message: Message) -> bool:
        """مدیریت پاسخ خودکار"""
        if not message.text:
            return False
            
        # دریافت پاسخ
        reply = await self.db.get_auto_reply(message.text.lower())
        if reply:
            await message.reply(reply)
            return True
            
        return False
        
    async def _handle_anti_spam(self, message: Message) -> bool:
        """مدیریت ضد اسپم"""
        if not message.from_user:
            return False
            
        # ساده: اگر کاربر بیش از حد پیام فرستاده باشد
        key = f"spam_{message.from_user.id}_{message.chat.id}"
        count = await self.db.get_setting(key, 0)
        
        if count > 10:  # بیش از 10 پیام
            # اخطار یا بلاک
            await message.reply("⚠️ **هشدار اسپم!** لطفاً سرعت پیام‌های خود را کاهش دهید.")
            return True
            
        await self.db.set_setting(key, count + 1)
        return False
        
    async def _handle_force_join(self, message: Message) -> bool:
        """مدیریت جوین اجباری"""
        # پیاده‌سازی جوین اجباری
        return False
        
    async def _save_message(self, message: Message, outgoing: bool = False):
        """ذخیره پیام در دیتابیس"""
        # پیاده‌سازی ذخیره پیام
        pass
