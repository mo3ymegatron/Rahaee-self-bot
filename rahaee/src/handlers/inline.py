# src/handlers/inline.py

import asyncio
import json
from typing import Optional, List, Dict, Any
from pyrogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from pyrogram.types import InlineQueryResultPhoto, InlineQueryResultDocument, InlineQueryResultAudio
import re

from core.logger import get_logger
from core.database import Database
from core.config import Config


class InlineHandler:
    """مدیریت هندلرهای Inline Mode"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger("inline_handler")
        self.db = bot.db
        self.config = bot.config
        self.client = bot.client
        
        # کش برای نتایج
        self.cache = {}
        self.cache_timeout = 300  # 5 دقیقه
        
    async def handle(self, client, inline_query: InlineQuery):
        """هندلر اصلی Inline Query"""
        try:
            query = inline_query.query or ""
            user_id = inline_query.from_user.id
            
            # بررسی دسترسی
            if not self.config.is_owner(user_id):
                user = await self.db.get_user(user_id)
                if not user or not user.get('is_admin'):
                    await inline_query.answer([], cache_time=60)
                    return
            
            # پردازش کوئری
            if query == "panel":
                await self._panel_inline(inline_query)
            elif query == "help":
                await self._help_inline(inline_query)
            elif query == "stats":
                await self._stats_inline(inline_query)
            elif query.startswith("user_"):
                await self._user_info_inline(inline_query, query)
            elif query.startswith("search_"):
                await self._search_inline(inline_query, query)
            elif query.startswith("translate_"):
                await self._translate_inline(inline_query, query)
            elif query.startswith("weather_"):
                await self._weather_inline(inline_query, query)
            elif query.startswith("calc_"):
                await self._calc_inline(inline_query, query)
            else:
                await self._default_inline(inline_query, query)
                
        except FloodWait as e:
            self.logger.warning(f"FloodWait: {e.x}s")
            await asyncio.sleep(e.x)
        except Exception as e:
            self.logger.error(f"Error in inline handler: {e}")
            await inline_query.answer([], cache_time=60)
            
    # ============================================================
    # نتایج Inline
    # ============================================================
    
    async def _panel_inline(self, inline_query: InlineQuery):
        """پنل مدیریت به صورت Inline"""
        results = []
        
        # دکمه‌های پنل
        panel_text = """
**🔰 پنل مدیریت رهایی**

📱 **توسعه‌دهنده:** @UXlor
📌 **نسخه:** 1.0.0

برای استفاده از دکمه‌های زیر کلیک کنید:
"""
        
        buttons = [
            [
                InlineKeyboardButton("📖 راهنما", callback_data="help"),
                InlineKeyboardButton("📊 آمار", callback_data="full_stats")
            ],
            [
                InlineKeyboardButton("👥 کاربران", callback_data="manage_users"),
                InlineKeyboardButton("💬 گروه‌ها", callback_data="manage_groups")
            ],
            [
                InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings"),
                InlineKeyboardButton("🔄 بکاپ", callback_data="backup_now")
            ],
            [
                InlineKeyboardButton("📱 پشتیبانی", url="https://t.me/UXlor")
            ]
        ]
        
        result = InlineQueryResultArticle(
            id="panel",
            title="🔰 پنل مدیریت",
            description="پنل کامل مدیریت رهایی",
            input_message_content=InputTextMessageContent(
                panel_text,
                parse_mode="markdown"
            ),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
        results.append(result)
        
        await inline_query.answer(results, cache_time=60)
        
    async def _help_inline(self, inline_query: InlineQuery):
        """راهنما به صورت Inline"""
        help_text = """
**📖 راهنمای سریع رهایی**

🔥 **دستورات اصلی:**
`.help` - راهنما
`.panel` - پنل
`.ping` - تست سرعت
`.stats` - آمار

👤 **پروفایل:**
`.setname` - تغییر نام
`.setbio` - تغییر بیو
`.setphoto` - تغییر عکس

👮 **مدیریت گروه:**
`.ban` - اخراج
`.unban` - رفع اخراج
`.mute` - سکوت
`.unmute` - رفع سکوت

🛠 **ابزارها:**
`.ocr` - تشخیص متن
`.qrcode` - QR Code
`.translate` - ترجمه
`.weather` - آب و هوا
`.calc` - ماشین حساب

💬 **منشی:**
`.addreply` - افزودن پاسخ
`.removereply` - حذف پاسخ
`.listreply` - لیست پاسخ‌ها

📱 **توسعه‌دهنده:** @UXlor
"""
        result = InlineQueryResultArticle(
            id="help",
            title="📖 راهنما",
            description="راهنمای کامل دستورات رهایی",
            input_message_content=InputTextMessageContent(
                help_text,
                parse_mode="markdown"
            )
        )
        
        await inline_query.answer([result], cache_time=300)
        
    async def _stats_inline(self, inline_query: InlineQuery):
        """آمار به صورت Inline"""
        try:
            total_stats = await self.db.get_total_stats()
            daily_stats = await self.db.get_daily_stats()
            
            stats_text = f"""
📊 **آمار سریع رهایی**

📈 **آمار کلی:**
• 👥 کاربران: {total_stats.get('total_users', 0)}
• 💬 گروه‌ها: {total_stats.get('total_groups', 0)}
• 📨 پیام‌ها: {total_stats.get('total_messages', 0)}

📊 **آمار امروز:**
• 📤 ارسال: {daily_stats.get('messages_sent', 0)}
• 📥 دریافت: {daily_stats.get('messages_received', 0)}
• 🎯 دستورات: {daily_stats.get('commands_used', 0)}
• 👤 کاربران جدید: {daily_stats.get('new_users', 0)}

📱 @UXlor
"""
            result = InlineQueryResultArticle(
                id="stats",
                title="📊 آمار",
                description="مشاهده آمار رهایی",
                input_message_content=InputTextMessageContent(
                    stats_text,
                    parse_mode="markdown"
                )
            )
            
            await inline_query.answer([result], cache_time=120)
            
        except Exception as e:
            self.logger.error(f"Stats inline error: {e}")
            await inline_query.answer([], cache_time=60)
            
    async def _user_info_inline(self, inline_query: InlineQuery, query: str):
        """اطلاعات کاربر به صورت Inline"""
        try:
            # استخراج آیدی
            user_id = query.replace("user_", "")
            if not user_id:
                await inline_query.answer([], cache_time=60)
                return
                
            # دریافت اطلاعات
            user_info = await self.client.get_user_info(int(user_id))
            if not user_info:
                await inline_query.answer([], cache_time=60)
                return
                
            user_data = await self.db.get_user(int(user_id))
            
            text = f"""
👤 **اطلاعات کاربر**

📝 **نام:** {user_info.first_name or 'نامشخص'}
🆔 **آیدی:** `{user_id}`
🔖 **یوزرنیم:** @{user_info.username or 'ندارد'}

📊 **آمار:**
• پیام‌ها: {user_data.get('message_count', 0) if user_data else 0}
• دستورات: {user_data.get('command_count', 0) if user_data else 0}
• عضویت: {user_data.get('created_at', 'نامشخص') if user_data else 'نامشخص'}

✅ **وضعیت:** {'مدیر' if user_data and user_data.get('is_admin') else 'کاربر عادی'}
"""
            
            result = InlineQueryResultArticle(
                id=f"user_{user_id}",
                title=f"👤 {user_info.first_name or 'کاربر'}",
                description=f"آیدی: {user_id}",
                input_message_content=InputTextMessageContent(
                    text,
                    parse_mode="markdown"
                )
            )
            
            await inline_query.answer([result], cache_time=60)
            
        except Exception as e:
            self.logger.error(f"User info inline error: {e}")
            await inline_query.answer([], cache_time=60)
            
    async def _search_inline(self, inline_query: InlineQuery, query: str):
        """جستجو به صورت Inline"""
        try:
            search_term = query.replace("search_", "").strip()
            if not search_term or len(search_term) < 2:
                await inline_query.answer([], cache_time=60)
                return
                
            # جستجو در کاربران
            users = await self.db.get_all_users()
            results = []
            
            for user in users[:20]:  # حداکثر ۲۰ نتیجه
                user_info = await self.client.get_user_info(user['id'])
                if not user_info:
                    continue
                    
                name = user_info.first_name or ""
                username = user_info.username or ""
                
                if search_term.lower() in name.lower() or search_term.lower() in username.lower():
                    result = InlineQueryResultArticle(
                        id=f"user_{user['id']}",
                        title=f"👤 {name}",
                        description=f"@{username} | آیدی: {user['id']}",
                        input_message_content=InputTextMessageContent(
                            f"👤 **کاربر:** {name}\n🆔 **آیدی:** `{user['id']}`\n🔖 **یوزرنیم:** @{username}",
                            parse_mode="markdown"
                        )
                    )
                    results.append(result)
                    
            await inline_query.answer(results[:50], cache_time=120)
            
        except Exception as e:
            self.logger.error(f"Search inline error: {e}")
            await inline_query.answer([], cache_time=60)
            
    async def _translate_inline(self, inline_query: InlineQuery, query: str):
        """ترجمه به صورت Inline"""
        try:
            text = query.replace("translate_", "").strip()
            if not text:
                await inline_query.answer([], cache_time=60)
                return
                
            # ترجمه با Google Translate
            try:
                from googletrans import Translator
                translator = Translator()
                result = translator.translate(text, dest='fa')
                
                translation_text = f"""
🌐 **ترجمه**

**متن اصلی:**
`{text}`

**ترجمه به فارسی:**
`{result.text}`

📍 زبان: {result.src} → fa
"""
                result_article = InlineQueryResultArticle(
                    id="translate",
                    title="🌐 ترجمه",
                    description=f"{result.text[:50]}...",
                    input_message_content=InputTextMessageContent(
                        translation_text,
                        parse_mode="markdown"
                    )
                )
                
                await inline_query.answer([result_article], cache_time=300)
                
            except ImportError:
                await inline_query.answer([], cache_time=60)
                
        except Exception as e:
            self.logger.error(f"Translate inline error: {e}")
            await inline_query.answer([], cache_time=60)
            
    async def _weather_inline(self, inline_query: InlineQuery, query: str):
        """آب و هوا به صورت Inline"""
        try:
            city = query.replace("weather_", "").strip()
            if not city:
                await inline_query.answer([], cache_time=60)
                return
                
            import requests
            
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.config.WEATHER_API_KEY}&units=metric&lang=fa"
            
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get('cod') != 200:
                await inline_query.answer([], cache_time=60)
                return
                
            weather_text = f"""
🌤 **آب و هوای {city}**

🌡 **دما:** {data['main']['temp']}°C
🤔 **احساس:** {data['main']['feels_like']}°C
🌧 **وضعیت:** {data['weather'][0]['description']}
💧 **رطوبت:** {data['main']['humidity']}%
💨 **باد:** {data['wind']['speed']} m/s
"""
            result = InlineQueryResultArticle(
                id="weather",
                title=f"🌤 آب و هوای {city}",
                description=f"{data['main']['temp']}°C - {data['weather'][0]['description']}",
                input_message_content=InputTextMessageContent(
                    weather_text,
                    parse_mode="markdown"
                )
            )
            
            await inline_query.answer([result], cache_time=600)  # ۱۰ دقیقه کش
            
        except Exception as e:
            self.logger.error(f"Weather inline error: {e}")
            await inline_query.answer([], cache_time=60)
            
    async def _calc_inline(self, inline_query: InlineQuery, query: str):
        """ماشین حساب به صورت Inline"""
        try:
            expression = query.replace("calc_", "").strip()
            if not expression:
                await inline_query.answer([], cache_time=60)
                return
                
            # محاسبه امن
            result = eval(expression, {"__builtins__": {}})
            
            calc_text = f"""
🧮 **ماشین حساب**

📝 `{expression}` = `{result}`
"""
            result_article = InlineQueryResultArticle(
                id="calc",
                title=f"🧮 {expression} = {result}",
                description=f"نتیجه: {result}",
                input_message_content=InputTextMessageContent(
                    calc_text,
                    parse_mode="markdown"
                )
            )
            
            await inline_query.answer([result_article], cache_time=300)
            
        except Exception as e:
            # نمایش خطا
            error_result = InlineQueryResultArticle(
                id="calc_error",
                title="❌ عبارت نامعتبر",
                description=str(e),
                input_message_content=InputTextMessageContent(
                    f"❌ **خطا:** `{e}`",
                    parse_mode="markdown"
                )
            )
            await inline_query.answer([error_result], cache_time=60)
            
    async def _default_inline(self, inline_query: InlineQuery, query: str):
        """حالت پیش‌فرض Inline"""
        # اگر کوئری با دستور خاصی مطابقت نداشت
        results = []
        
        # گزینه‌های پیشنهادی
        suggestions = [
            ("🔰 پنل", "panel", "پنل مدیریت رهایی"),
            ("📖 راهنما", "help", "راهنمای کامل دستورات"),
            ("📊 آمار", "stats", "مشاهده آمار رهایی"),
            ("🌐 ترجمه", "translate_", "ترجمه متن به فارسی"),
            ("🌤 آب و هوا", "weather_", "اطلاعات آب و هوای شهر"),
            ("🧮 ماشین حساب", "calc_", "محاسبه عبارات ریاضی"),
            ("👤 جستجو", "search_", "جستجوی کاربران"),
        ]
        
        for title, cmd, desc in suggestions:
            if query and not query.startswith(cmd):
                continue
                
            result = InlineQueryResultArticle(
                id=f"default_{cmd}",
                title=title,
                description=desc,
                input_message_content=InputTextMessageContent(
                    f"**🔍 استفاده از {title}**\n\n"
                    f"برای استفاده، دستور زیر را تایپ کنید:\n"
                    f"`@{self.client.app.me.username} {cmd}...`\n\n"
                    f"📱 @UXlor",
                    parse_mode="markdown"
                )
            )
            results.append(result)
            
        if not results:
            # نتیجه پیش‌فرض
            results.append(
                InlineQueryResultArticle(
                    id="default",
                    title="🔍 جستجو",
                    description="برای جستجو، عبارت را وارد کنید",
                    input_message_content=InputTextMessageContent(
                        "**🔍 جستجو در رهایی**\n\n"
                        "برای جستجوی کاربران:\n"
                        f"`@{self.client.app.me.username} search_نام`\n\n"
                        "📱 @UXlor",
                        parse_mode="markdown"
                    )
                )
            )
            
        await inline_query.answer(results[:50], cache_time=120)
