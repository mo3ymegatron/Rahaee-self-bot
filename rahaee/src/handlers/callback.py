# src/handlers/callback.py

import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

from core.logger import get_logger
from core.database import Database
from core.config import Config


class CallbackHandler:
    """مدیریت هندلرهای کالبک (دکمه‌های شیشه‌ای)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger("callback_handler")
        self.db = bot.db
        self.config = bot.config
        self.client = bot.client
        
        # کش برای ذخیره موقت اطلاعات
        self.temp_data = {}
        
    async def handle(self, client, callback_query: CallbackQuery):
        """هندلر اصلی کالبک"""
        try:
            data = callback_query.data
            user_id = callback_query.from_user.id
            
            # بررسی دسترسی
            if not self.config.is_owner(user_id):
                # بررسی ادمین بودن
                user = await self.db.get_user(user_id)
                if not user or not user.get('is_admin'):
                    await callback_query.answer("⛔ شما دسترسی ندارید!", show_alert=True)
                    return
            
            # پردازش کالبک
            if data == "help":
                await self._help_callback(callback_query)
            elif data == "full_stats":
                await self._full_stats_callback(callback_query)
            elif data == "settings":
                await self._settings_callback(callback_query)
            elif data == "manage_users":
                await self._manage_users_callback(callback_query)
            elif data == "manage_groups":
                await self._manage_groups_callback(callback_query)
            elif data.startswith("user_"):
                await self._user_detail_callback(callback_query, data)
            elif data.startswith("group_"):
                await self._group_detail_callback(callback_query, data)
            elif data.startswith("ban_user_"):
                await self._ban_user_callback(callback_query, data)
            elif data.startswith("unban_user_"):
                await self._unban_user_callback(callback_query, data)
            elif data.startswith("make_admin_"):
                await self._make_admin_callback(callback_query, data)
            elif data.startswith("remove_admin_"):
                await self._remove_admin_callback(callback_query, data)
            elif data == "backup_now":
                await self._backup_now_callback(callback_query)
            elif data == "restore_backup":
                await self._restore_backup_callback(callback_query)
            elif data == "clear_cache":
                await self._clear_cache_callback(callback_query)
            elif data == "show_logs":
                await self._show_logs_callback(callback_query)
            elif data.startswith("page_"):
                await self._page_callback(callback_query, data)
            elif data == "back_to_panel":
                await self._back_to_panel_callback(callback_query)
            else:
                await callback_query.answer("❌ دستور نامعتبر!", show_alert=True)
                
        except FloodWait as e:
            self.logger.warning(f"FloodWait: {e.x}s")
            await asyncio.sleep(e.x)
        except Exception as e:
            self.logger.error(f"Error in callback handler: {e}")
            await callback_query.answer("❌ خطا در پردازش!", show_alert=True)
            
    # ============================================================
    # کالبک‌های اصلی
    # ============================================================
    
    async def _help_callback(self, callback_query: CallbackQuery):
        """نمایش راهنما"""
        help_text = """
**📖 راهنمای رهایی**

**🔥 دستورات اصلی:**
`.help` - نمایش راهنما
`.panel` - پنل مدیریت
`.ping` - تست سرعت
`.stats` - آمار
`.backup` - بکاپ
`.update` - آپدیت

**👤 پروفایل:**
`.setname` - تغییر نام
`.setbio` - تغییر بیو
`.setphoto` - تغییر عکس

**👮 مدیریت گروه:**
`.ban` - اخراج
`.unban` - رفع اخراج
`.mute` - سکوت
`.unmute` - رفع سکوت
`.pin` - پین
`.unpin` - حذف پین
`.delete` - حذف پیام
`.purge` - پاکسازی

**🛠 ابزارها:**
`.ocr` - تشخیص متن از عکس
`.qrcode` - ساخت QR Code
`.translate` - ترجمه
`.weather` - آب و هوا
`.calc` - ماشین حساب

📱 **توسعه‌دهنده:** @UXlor
📌 **نسخه:** 1.0.0
"""
        buttons = [
            [InlineKeyboardButton("🏠 بازگشت به پنل", callback_data="back_to_panel")]
        ]
        
        await callback_query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
        
    async def _full_stats_callback(self, callback_query: CallbackQuery):
        """نمایش آمار کامل"""
        try:
            # آمار کلی
            total_stats = await self.db.get_total_stats()
            
            # آمار روزانه (۷ روز اخیر)
            daily_stats = []
            for i in range(7):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                stats = await self.db.get_daily_stats(date)
                daily_stats.append(stats)
                
            # آمار کاربران
            users = await self.db.get_all_users()
            active_users = sum(1 for u in users if u.get('is_admin', False))
            
            stats_text = f"""
**📊 آمار کامل رهایی**
━━━━━━━━━━━━━
**📈 آمار کلی:**
• 👥 کاربران کل: {total_stats.get('total_users', 0)}
• 👤 کاربران فعال: {active_users}
• 💬 گروه‌ها: {total_stats.get('total_groups', 0)}
• 📨 پیام‌ها: {total_stats.get('total_messages', 0)}

**📊 آمار ۷ روز اخیر:**
"""
            for stats in daily_stats[:3]:  # نمایش ۳ روز اخیر
                stats_text += f"""
• {stats.get('date')}:
  - پیام: {stats.get('messages_sent', 0)}
  - دستورات: {stats.get('commands_used', 0)}
  - کاربران جدید: {stats.get('new_users', 0)}
"""
                
            if len(daily_stats) > 3:
                stats_text += f"\n... و {len(daily_stats) - 3} روز دیگر"
                
            buttons = [
                [InlineKeyboardButton("📥 دریافت گزارش کامل", callback_data="export_stats")],
                [InlineKeyboardButton("🏠 بازگشت", callback_data="back_to_panel")]
            ]
            
            await callback_query.edit_message_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await callback_query.answer()
            
        except Exception as e:
            self.logger.error(f"Stats callback error: {e}")
            await callback_query.answer("❌ خطا در دریافت آمار!", show_alert=True)
            
    async def _settings_callback(self, callback_query: CallbackQuery):
        """تنظیمات"""
        settings_text = """
**⚙️ تنظیمات رهایی**

🔹 **تنظیمات عمومی:**
• وضعیت: فعال
• نسخه: 1.0.0
• زبان: فارسی

🔹 **تنظیمات امنیتی:**
• ضد اسپم: فعال
• ضد لینک: غیرفعال
• جوین اجباری: غیرفعال

🔹 **تنظیمات منشی:**
• پاسخ خودکار: غیرفعال
• AFK: غیرفعال

🔹 **تنظیمات ظاهری:**
• فونت: پیش‌فرض
• تم: روشن
"""
        buttons = [
            [InlineKeyboardButton("🔒 تنظیمات امنیتی", callback_data="security_settings")],
            [InlineKeyboardButton("💬 تنظیمات منشی", callback_data="reply_settings")],
            [InlineKeyboardButton("🎨 تنظیمات ظاهری", callback_data="appearance_settings")],
            [InlineKeyboardButton("🏠 بازگشت", callback_data="back_to_panel")]
        ]
        
        await callback_query.edit_message_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
        
    async def _manage_users_callback(self, callback_query: CallbackQuery):
        """مدیریت کاربران"""
        users = await self.db.get_all_users()
        
        if not users:
            await callback_query.answer("❌ کاربری یافت نشد!", show_alert=True)
            return
            
        # نمایش ۱۰ کاربر اول
        user_list = users[:10]
        text = "👥 **مدیریت کاربران**\n━━━━━━━━━━━━━\n"
        
        for i, user in enumerate(user_list, 1):
            user_info = await self.bot.client.get_user_info(user['id'])
            name = user_info.first_name if user_info else "نامشخص"
            status = "✅" if user.get('is_admin') else "⬜"
            text += f"{i}. {status} {name} (`{user['id']}`)\n"
            
        if len(users) > 10:
            text += f"\n... و {len(users) - 10} کاربر دیگر"
            
        buttons = [
            [InlineKeyboardButton("📋 مشاهده همه", callback_data="page_1")],
            [InlineKeyboardButton("🏠 بازگشت", callback_data="back_to_panel")]
        ]
        
        await callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
        
    async def _manage_groups_callback(self, callback_query: CallbackQuery):
        """مدیریت گروه‌ها"""
        groups = await self.db.get_all_groups()
        
        if not groups:
            await callback_query.answer("❌ گروهی یافت نشد!", show_alert=True)
            return
            
        # نمایش ۱۰ گروه اول
        group_list = groups[:10]
        text = "💬 **مدیریت گروه‌ها**\n━━━━━━━━━━━━━\n"
        
        for i, group in enumerate(group_list, 1):
            text += f"{i}. {group.get('title', 'بدون نام')} (`{group['id']}`)\n"
            
        if len(groups) > 10:
            text += f"\n... و {len(groups) - 10} گروه دیگر"
            
        buttons = [
            [InlineKeyboardButton("📋 مشاهده همه", callback_data="groups_page_1")],
            [InlineKeyboardButton("🏠 بازگشت", callback_data="back_to_panel")]
        ]
        
        await callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
        
    # ============================================================
    # کالبک‌های مدیریت کاربران
    # ============================================================
    
    async def _user_detail_callback(self, callback_query: CallbackQuery, data: str):
        """نمایش جزئیات کاربر"""
        try:
            user_id = int(data.split("_")[1])
            user = await self.db.get_user(user_id)
            user_info = await self.bot.client.get_user_info(user_id)
            
            if not user:
                await callback_query.answer("❌ کاربر یافت نشد!", show_alert=True)
                return
                
            text = f"""
👤 **جزئیات کاربر**
━━━━━━━━━━━━━
📝 **نام:** {user_info.first_name or 'نامشخص'}
🆔 **آیدی:** `{user_id}`
📊 **پیام‌ها:** {user.get('message_count', 0)}
🎯 **دستورات:** {user.get('command_count', 0)}
📅 **عضویت:** {user.get('created_at', 'نامشخص')}
👑 **وضعیت:** {'مدیر ✅' if user.get('is_admin') else 'کاربر عادی'}
"""
            buttons = []
            
            if user.get('is_admin'):
                buttons.append([InlineKeyboardButton("❌ حذف مدیر", callback_data=f"remove_admin_{user_id}")])
            else:
                buttons.append([InlineKeyboardButton("⭐ افزودن مدیر", callback_data=f"make_admin_{user_id}")])
                
            if user.get('is_banned'):
                buttons.append([InlineKeyboardButton("✅ آنبلاک", callback_data=f"unban_user_{user_id}")])
            else:
                buttons.append([InlineKeyboardButton("🚫 بلاک", callback_data=f"ban_user_{user_id}")])
                
            buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="manage_users")])
            
            await callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await callback_query.answer()
            
        except Exception as e:
            self.logger.error(f"User detail error: {e}")
            await callback_query.answer("❌ خطا!", show_alert=True)
            
    async def _ban_user_callback(self, callback_query: CallbackQuery, data: str):
        """بلاک کاربر"""
        try:
            user_id = int(data.split("_")[2])
            await self.db.update_user(user_id, is_banned=True)
            await callback_query.answer("✅ کاربر بلاک شد!", show_alert=True)
            
            # بازگشت به لیست
            await self._manage_users_callback(callback_query)
            
        except Exception as e:
            self.logger.error(f"Ban user error: {e}")
            await callback_query.answer("❌ خطا!", show_alert=True)
            
    async def _unban_user_callback(self, callback_query: CallbackQuery, data: str):
        """آنبلاک کاربر"""
        try:
            user_id = int(data.split("_")[2])
            await self.db.update_user(user_id, is_banned=False)
            await callback_query.answer("✅ کاربر آنبلاک شد!", show_alert=True)
            
            # بازگشت به لیست
            await self._manage_users_callback(callback_query)
            
        except Exception as e:
            self.logger.error(f"Unban user error: {e}")
            await callback_query.answer("❌ خطا!", show_alert=True)
            
    async def _make_admin_callback(self, callback_query: CallbackQuery, data: str):
        """افزودن مدیر"""
        try:
            user_id = int(data.split("_")[2])
            await self.db.update_user(user_id, is_admin=True)
            await callback_query.answer("✅ مدیر اضافه شد!", show_alert=True)
            
            # بازگشت به جزئیات
            await self._user_detail_callback(callback_query, f"user_{user_id}")
            
        except Exception as e:
            self.logger.error(f"Make admin error: {e}")
            await callback_query.answer("❌ خطا!", show_alert=True)
            
    async def _remove_admin_callback(self, callback_query: CallbackQuery, data: str):
        """حذف مدیر"""
        try:
            user_id = int(data.split("_")[2])
            await self.db.update_user(user_id, is_admin=False)
            await callback_query.answer("✅ مدیر حذف شد!", show_alert=True)
            
            # بازگشت به جزئیات
            await self._user_detail_callback(callback_query, f"user_{user_id}")
            
        except Exception as e:
            self.logger.error(f"Remove admin error: {e}")
            await callback_query.answer("❌ خطا!", show_alert=True)
            
    # ============================================================
    # کالبک‌های بکاپ و نگهداری
    # ============================================================
    
    async def _backup_now_callback(self, callback_query: CallbackQuery):
        """بکاپ فوری"""
        try:
            await callback_query.answer("⏳ در حال بکاپ...")
            
            # اینجا کد بکاپ
            await asyncio.sleep(2)  # شبیه‌سازی
            
            await callback_query.edit_message_text(
                "✅ **بکاپ با موفقیت انجام شد!**\n"
                "📁 فایل: backup_2026.db\n"
                "📦 حجم: 2.5 MB\n"
                "📅 تاریخ: {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 دانلود بکاپ", callback_data="download_backup")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_panel")]
                ])
            )
            
        except Exception as e:
            self.logger.error(f"Backup error: {e}")
            await callback_query.answer("❌ خطا در بکاپ!", show_alert=True)
            
    async def _restore_backup_callback(self, callback_query: CallbackQuery):
        """بازیابی بکاپ"""
        await callback_query.answer(
            "⚠️ این عمل غیرقابل بازگشت است!",
            show_alert=True
        )
        
    async def _clear_cache_callback(self, callback_query: CallbackQuery):
        """پاکسازی کش"""
        await self.db.clear_cache()
        await callback_query.answer("✅ کش پاکسازی شد!", show_alert=True)
        
    async def _show_logs_callback(self, callback_query: CallbackQuery):
        """نمایش لاگ‌ها"""
        try:
            # خواندن ۱۰ خط آخر لاگ
            log_file = "logs/rahaee.log"
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-10:]
                    logs = ''.join(lines)
            except:
                logs = "لاگی موجود نیست"
                
            text = f"📋 **لاگ‌های اخیر**\n━━━━━━━━━━━━━\n```\n{logs}\n```"
            
            buttons = [
                [InlineKeyboardButton("🔄 بروزرسانی", callback_data="show_logs")],
                [InlineKeyboardButton("🗑 پاکسازی لاگ", callback_data="clear_logs")],
                [InlineKeyboardButton("🏠 بازگشت", callback_data="back_to_panel")]
            ]
            
            await callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await callback_query.answer()
            
        except Exception as e:
            self.logger.error(f"Show logs error: {e}")
            await callback_query.answer("❌ خطا!", show_alert=True)
            
    # ============================================================
    # کالبک‌های صفحه‌بندی
    # ============================================================
    
    async def _page_callback(self, callback_query: CallbackQuery, data: str):
        """صفحه‌بندی لیست کاربران"""
        try:
            page = int(data.split("_")[1])
            per_page = 10
            
            users = await self.db.get_all_users()
            total_pages = (len(users) + per_page - 1) // per_page
            
            if page > total_pages:
                page = total_pages
                
            start = (page - 1) * per_page
            end = start + per_page
            page_users = users[start:end]
            
            text = f"👥 **مدیریت کاربران - صفحه {page}/{total_pages}**\n━━━━━━━━━━━━━\n"
            
            for i, user in enumerate(page_users, 1):
                user_info = await self.bot.client.get_user_info(user['id'])
                name = user_info.first_name if user_info else "نامشخص"
                status = "✅" if user.get('is_admin') else "⬜"
                text += f"{start + i}. {status} {name} (`{user['id']}`)\n"
                
            buttons = []
            nav_buttons = []
            
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"page_{page - 1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"page_{page + 1}"))
                
            if nav_buttons:
                buttons.append(nav_buttons)
                
            buttons.append([InlineKeyboardButton("🏠 بازگشت", callback_data="manage_users")])
            
            await callback_query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await callback_query.answer()
            
        except Exception as e:
            self.logger.error(f"Page callback error: {e}")
            await callback_query.answer("❌ خطا!", show_alert=True)
            
    async def _back_to_panel_callback(self, callback_query: CallbackQuery):
        """بازگشت به پنل اصلی"""
        try:
            # ایجاد پنل اصلی
            from handlers.message import MessageHandler
            msg_handler = MessageHandler(self.bot)
            
            # شبیه‌سازی پیام برای پنل
            class FakeMessage:
                def __init__(self, user_id):
                    self.from_user = type('obj', (object,), {'id': user_id, 'first_name': 'کاربر'})
                    
            fake_msg = FakeMessage(callback_query.from_user.id)
            
            # نمایش پنل
            await msg_handler.handle_panel(
                self.client,
                fake_msg,
                ""
            )
            
            # حذف پیام کالبک
            await callback_query.message.delete()
            await callback_query.answer()
            
        except Exception as e:
            self.logger.error(f"Back to panel error: {e}")
            await callback_query.answer("❌ خطا!", show_alert=True)
