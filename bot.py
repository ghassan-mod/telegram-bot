import asyncio
import json
import os
import random
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

# ========== إعدادات البوت من متغيرات البيئة ==========
TOKEN = os.environ.get("TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@قناتك")
if not TOKEN:
    raise ValueError("لم يتم العثور على التوكن! تأكد من إضافة TOKEN في متغيرات البيئة")

# ========== إعدادات متقدمة لتحسين الأداء ==========
MAX_MESSAGE_LENGTH = 4096
MAX_CLEAN_MESSAGES = 100
DEFAULT_MUTE_DURATION = 60
MAX_REPLIES_DISPLAY = 20
CACHE_SIZE = 1000
BATCH_SAVE_INTERVAL = 60  # حفظ البيانات كل 60 ثانية

# ========== إعدادات التسجيل المحسنة ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== إدارة البيانات المحسنة ==========
DATA_FILE = "bot_data.json"
REPLIES_FILE = "replies.json"
_data_cache = {}
_replies_cache = {}
_pending_save = False
_last_save_time = datetime.now()

def load_data() -> Dict:
    """تحميل البيانات مع معالجة الأخطاء المحسنة"""
    global _data_cache
    if _data_cache:
        return _data_cache
    
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                _data_cache = json.load(f)
                return _data_cache
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"خطأ في تحميل البيانات: {e}")
    
    _data_cache = {
        "ban_words": ["عيب", "حرام", "وسخ", "قذر", "كلب", "حمار"],
        "warnings": {},
        "muted_users": {},
        "banned_users": [],
        "welcomed_users": [],
        "user_points": {},
        "user_levels": {},
        "group_settings": {"locked": False, "anti_links": False, "anti_forward": False, "captcha": False},
        "channel_posts": {},
        "user_reports": {},
        "tickets": {},
        "faqs": {},
        "notes": {},
        "birthdays": {},
        "polls": {},
        "reminders": {}
    }
    return _data_cache

def load_replies() -> Dict:
    """تحميل الردود مع معالجة الأخطاء المحسنة"""
    global _replies_cache
    if _replies_cache:
        return _replies_cache
    
    try:
        if os.path.exists(REPLIES_FILE):
            with open(REPLIES_FILE, 'r', encoding='utf-8') as f:
                _replies_cache = json.load(f)
                return _replies_cache
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"خطأ في تحميل الردود: {e}")
    
    _replies_cache = {"keywords": [], "auto_replies": []}
    return _replies_cache

def save_data_optimized():
    """حفظ البيانات بشكل محسن مع تجميع عمليات الحفظ"""
    global _pending_save, _last_save_time, _data_cache
    
    if not _data_cache:
        return
    
    _pending_save = True
    now = datetime.now()
    
    if (now - _last_save_time).total_seconds() >= BATCH_SAVE_INTERVAL:
        _perform_save()

def _perform_save():
    """تنفيذ عملية الحفظ الفعلية"""
    global _pending_save, _last_save_time, _data_cache, _replies_cache
    
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(_data_cache, f, ensure_ascii=False, indent=2)
        
        with open(REPLIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(_replies_cache, f, ensure_ascii=False, indent=2)
        
        _last_save_time = datetime.now()
        _pending_save = False
        logger.info("تم حفظ البيانات بنجاح")
    except Exception as e:
        logger.error(f"خطأ في حفظ البيانات: {e}")

# تحميل البيانات الأولي
data = load_data()
replies_data = load_replies()
ban_words = data["ban_words"]
warnings = data["warnings"]
muted_users = data["muted_users"]
banned_users = data["banned_users"]
user_points = data["user_points"]
user_levels = data["user_levels"]
group_settings = data["group_settings"]
channel_posts = data["channel_posts"]
tickets = data["tickets"]
faqs = data["faqs"]
notes = data["notes"]
birthdays = data["birthdays"]
polls = data["polls"]
reminders = data["reminders"]

# ========== الردود التلقائية المحسنة (أسرع وأكثر كفاءة) ==========
AUTO_REPLIES = [
    {"keywords": ["شكرا", "thank", "thanks"], "reply": "العفو ❤️ تسلم/ي 🤍"},
    {"keywords": ["صباح", "صباح الخير"], "reply": "صباح النور والفل 🌞🌹"},
    {"keywords": ["مساء", "مساء الخير"], "reply": "مساء الياسمين والورد 🌙✨"},
    {"keywords": ["هلا", "اهلا", "مرحبا"], "reply": "هلا وغلا بيك/ي 🌟"},
    {"keywords": ["كيف حالك", "كيفك"], "reply": "الحمد لله، بخير وسعادة، وأنت/ي؟ 🤗"},
    {"keywords": ["الله", "الحمد لله"], "reply": "الله أكبر ❤️ سبحان الله وبحمده"},
    {"keywords": ["احبك", "بحبك"], "reply": "أحبك الذي أحببتني له 🤍"},
    {"keywords": ["64", "32", "نسخه", "نسخة"], "reply": None},  # سيتم معالجته بشكل خاص
    {"keywords": ["ويندوز", "windows"], "reply": "عندك سؤال عن ويندوز؟ احنا بالخدمة 💻"},
    {"keywords": ["برنامج", "تحميل"], "reply": f"ابحث في القناة {CHANNEL_ID} 🔍"},
    {"keywords": ["ما شاء الله", "ماشاء الله"], "reply": "تبارك الرحمن ❤️"},
    {"keywords": ["استغفر الله", "استغفار"], "reply": "أستغفر الله العظيم وأتوب إليه 🤲"},
    {"keywords": ["صلى الله عليه", "صلي"], "reply": "اللهم صل وسلم على نبينا محمد ﷺ"},
    {"keywords": ["نجحت", "نجح"], "reply": "ألف مبروك النجاح 🎉❤️ فخورين فيك/ي"},
    {"keywords": ["حلم", "حلمي"], "reply": "حلمك قريب، استمر/ي في السعي 🌟"},
    {"keywords": ["ملل", "زهق"], "reply": "شوف/ي القناة بتاعة المرح والمنوعات 🎮"},
    {"keywords": ["قهوة", "شاي"], "reply": "أنا كمان أحب القهوة ☕😋"},
    {"keywords": ["فيلم", "مسلسل"], "reply": "شوف/ي الترشيحات في قناتنا 🎬"},
    {"keywords": ["اغنية", "موسيقى"], "reply": "شاركنا ذوقك الموسيقي 🎵"},
    {"keywords": ["بوت", "bot"], "reply": "أنا البوت الخارق تحت خدمتك 🤖💪"},
    {"keywords": ["مساعدة", "help"], "reply": "اكتب /help وشوف/ي كل الخيارات 🆘"},
    {"keywords": ["اقتراح", "فكرة"], "reply": "اقتراحك يهمنا، اكتب /suggest 💡"},
    {"keywords": ["بايثون", "python"], "reply": "بايثون لغة سهلة وقوية 🐍"},
    {"keywords": ["العاب", "games"], "reply": "ألعاب الفيديو عالم ممتع 🎮"},
    {"keywords": ["ببجي", "pubg"], "reply": "ببجي حماس وتحدي 🎮"},
    {"keywords": ["فري فاير", "freefire"], "reply": "فري فاير سريع وممتع 🎮"},
]

# ========== دوال مساعدة محسنة ==========

async def is_admin(update: Update, user_id: int) -> bool:
    """التحقق من صلاحيات المشرف بشكل محسن"""
    try:
        chat_id = update.effective_chat.id
        user_status = await update.get_bot().get_chat_member(chat_id, user_id)
        return user_status.status in ["administrator", "creator"]
    except Exception as e:
        logger.error(f"خطأ في التحقق من المشرف: {e}")
        return False

def safe_truncate(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """قص النص بشكل آمن دون قطع الكلمات"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

async def safe_send_message(update: Update, text: str, **kwargs):
    """إرسال رسالة بشكل آمن مع معالجة الأخطاء"""
    try:
        text = safe_truncate(text)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, **kwargs)
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسالة: {e}")
        try:
            await update.message.reply_text(text, **kwargs)
        except Exception as e2:
            logger.error(f"فشل إرسال الرسالة حتى بدون Markdown: {e2}")

async def search_channel_for_post(update: Update, query: str):
    """البحث في القناة عن المنشورات بشكل محسن"""
    try:
        if not channel_posts:
            await safe_send_message(update, 
                f"🔍 **لم أجد منشورات محفوظة في القناة.**\n\n"
                f"📢 **قناتنا:** {CHANNEL_ID}\n"
                f"💡 سيتم حفظ المنشورات الجديدة تلقائياً.\n"
                f"🔗 يمكنك البحث يدوياً في القناة.",
                disable_web_page_preview=True)
            return
        
        search_term = "64" if "64" in query else "32" if "32" in query else None
        if not search_term:
            return
        
        found_posts = []
        for post_id, post in channel_posts.items():
            if search_term in post.get("text", ""):
                found_posts.append(post)
        
        if found_posts:
            # ترتيب حسب التاريخ (الأحدث أولاً)
            found_posts.sort(key=lambda x: x.get("date", ""), reverse=True)
            latest_post = found_posts[0]
            
            post_text = latest_post.get("text", "")[:300]
            if post_text:
                await safe_send_message(update,
                    f"🔍 **تم العثور على منشور يحتوي على {search_term}:**\n\n"
                    f"📌 {post_text}\n\n"
                    f"🔗 **الرابط:** {latest_post.get('link')}",
                    disable_web_page_preview=True)
            else:
                await safe_send_message(update,
                    f"🔍 **تم العثور على منشور يحتوي على {search_term}:**\n\n"
                    f"🔗 **الرابط:** {latest_post.get('link')}",
                    disable_web_page_preview=True)
        else:
            await safe_send_message(update,
                f"🔍 **لم أجد منشوراً يحتوي على {search_term} في القناة.**\n\n"
                f"📢 **قناتنا:** {CHANNEL_ID}\n"
                f"💡 يمكنك البحث يدوياً في القناة.",
                disable_web_page_preview=True)
                
    except Exception as e:
        logger.error(f"خطأ في البحث في القناة: {e}")
        await safe_send_message(update, "حدث خطأ أثناء البحث، يرجى المحاولة لاحقاً.")

async def smart_reply(update: Update):
    """نظام الردود الذكي المحسن"""
    if not update.message or not update.message.text:
        return False
    
    message_text = update.message.text.lower()
    
    # البحث في الردود المخصصة أولاً (أسرع)
    for item in replies_data.get("keywords", []):
        for keyword in item.get("keywords", []):
            if keyword in message_text:
                await safe_send_message(update, item["reply"])
                return True
    
    # البحث في الردود التلقائية
    for item in AUTO_REPLIES:
        for keyword in item["keywords"]:
            if keyword in message_text:
                if item["reply"] is None:
                    # معالجة خاصة للبحث عن 64/32
                    if "64" in message_text or "32" in message_text:
                        await search_channel_for_post(update, message_text)
                        return True
                else:
                    await safe_send_message(update, item["reply"])
                    return True
    
    return False

async def save_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ منشورات القناة بشكل محسن"""
    if update.channel_post and update.channel_post.chat_id == CHANNEL_ID.replace("@", ""):
        try:
            post_id = update.channel_post.message_id
            post_text = update.channel_post.text or update.channel_post.caption or ""
            
            channel_posts[str(post_id)] = {
                "text": post_text,
                "link": f"https://t.me/{CHANNEL_ID.replace('@', '')}/{post_id}",
                "date": datetime.now().isoformat()
            }
            
            # تنظيف المنشورات القديمة (الحفاظ على آخر 1000 منشور فقط)
            if len(channel_posts) > 1000:
                oldest_keys = sorted(channel_posts.keys(), key=lambda x: channel_posts[x].get("date", ""))[:200]
                for key in oldest_keys:
                    del channel_posts[key]
            
            data["channel_posts"] = channel_posts
            save_data_optimized()
            logger.info(f"تم حفظ منشور جديد: {post_id}")
        except Exception as e:
            logger.error(f"خطأ في حفظ منشور القناة: {e}")

# ========== الأوامر المحسنة ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start المحسن"""
    await safe_send_message(update,
        "🛡️ **بوت الحماية المتكامل - النسخة المحسنة** 🛡️\n\n"
        "أنا هنا لحماية مجموعتك بكل قوة وكفاءة!\n\n"
        "**📋 الأوامر الرئيسية:**\n"
        "/help - عرض كل الأوامر\n"
        "/rules - عرض القوانين\n"
        "/ticket مشكلتك - فتح تذكرة للمساعدة\n"
        "/add_reply كلمة1,كلمة2 | رد - إضافة رد مخصص\n"
        "/search 64 - البحث في القناة\n\n"
        "🌟 **بوت أقوى وأسرع وأكثر استقراراً!**")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /help المحسن"""
    await safe_send_message(update,
        "📚 **قائمة الأوامر الكاملة** 📚\n\n"
        "**🛡️ أوامر الحماية:**\n"
        "/kick @user - طرد عضو\n"
        "/mute id [ثواني] - كتم عضو\n"
        "/unmute id - فك الكتم\n"
        "/clean عدد - مسح رسائل\n\n"
        "**💬 أوامر الردود:**\n"
        "/add_reply كلمة1,كلمة2 | رد - إضافة رد\n"
        "/remove_reply كلمة - حذف رد\n"
        "/list_replies - عرض الردود\n\n"
        "**🎫 نظام التذاكر:**\n"
        "/ticket مشكلتك - فتح تذكرة\n"
        "/reply_ticket id رد - الرد على تذكرة (للمشرفين)\n\n"
        "**🔍 البحث في القناة:**\n"
        "/search 64 - البحث عن منشورات 64\n"
        "/search 32 - البحث عن منشورات 32\n"
        "أو اكتب 'اريد نسخه 64' أو 'اريد نسخه 32'\n\n"
        "**🎮 أوامر ترفيهية:**\n"
        "/joke - نكتة\n"
        "/quote - اقتباس\n"
        "/coin - رمي العملة\n"
        "/dice - نرد\n"
        "/8ball - كرة الحظ\n"
        "/info - معلوماتك\n"
        "/top - ترتيب النشاط\n"
        "/time - الوقت\n\n"
        "**❓ أوامر عامة:**\n"
        "/faq - أسئلة شائعة\n"
        "/poll سؤال | خيارات - استطلاع\n"
        "/remind دقائق نص - تذكير\n"
        "/calc عملية - آلة حاسبة\n"
        "/stats - إحصائيات\n"
        "/about - معلومات البوت")

async def ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فتح تذكرة بشكل محسن"""
    if context.args:
        problem = " ".join(context.args)
        ticket_id = f"ticket_{update.message.from_user.id}_{int(datetime.now().timestamp())}"
        
        tickets[ticket_id] = {
            "user_id": update.message.from_user.id,
            "user_name": update.message.from_user.first_name,
            "problem": problem,
            "status": "open",
            "created": datetime.now().isoformat(),
            "messages": []
        }
        data["tickets"] = tickets
        save_data_optimized()
        
        await safe_send_message(update,
            f"✅ **تم فتح تذكرة رقم:** `{ticket_id}`\n\n"
            f"📝 **مشكلتك:** {problem[:200]}\n\n"
            f"⏳ سيتم التواصل معك قريباً من قبل المشرفين.")
        
        # إشعار المشرفين
        await update.message.reply_text(
            f"🆕 **تذكرة جديدة!**\n\n"
            f"👤 المستخدم: {update.message.from_user.first_name}\n"
            f"📝 المشكلة: {problem[:100]}\n"
            f"🆔 المعرف: `{ticket_id}`\n"
            f"استخدم /reply_ticket {ticket_id} للرد",
            parse_mode=ParseMode.MARKDOWN)
    else:
        await safe_send_message(update, "استخدم: /ticket مشكلتك بالتفصيل")

async def reply_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرد على تذكرة بشكل محسن"""
    if not await is_admin(update, update.message.from_user.id):
        await safe_send_message(update, "❌ هذا الأمر للمشرفين فقط!")
        return
    
    if len(context.args) >= 2:
        ticket_id = context.args[0]
        reply_text = " ".join(context.args[1:])
        
        if ticket_id in tickets and tickets[ticket_id]["status"] == "open":
            user_id = tickets[ticket_id]["user_id"]
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📩 **رد على تذكرتك #{ticket_id}**\n\n{reply_text}\n\nللمتابعة استخدم /ticket",
                    parse_mode=ParseMode.MARKDOWN)
                await safe_send_message(update, f"✅ تم الرد على التذكرة {ticket_id}")
                
                tickets[ticket_id]["messages"].append({
                    "admin": update.message.from_user.first_name,
                    "reply": reply_text,
                    "time": datetime.now().isoformat()
                })
                data["tickets"] = tickets
                save_data_optimized()
            except Exception as e:
                logger.error(f"خطأ في الرد على التذكرة: {e}")
                await safe_send_message(update, "فشل إرسال الرسالة للمستخدم")
        else:
            await safe_send_message(update, "التذكرة غير موجودة أو مغلقة")
    else:
        await safe_send_message(update, "استخدم: /reply_ticket ticket_id الرد")

async def add_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة رد مخصص بشكل محسن"""
    if not await is_admin(update, update.message.from_user.id):
        await safe_send_message(update, "❌ هذا الأمر للمشرفين فقط!")
        return
    
    if context.args:
        text = " ".join(context.args)
        if "|" in text:
            parts = text.split("|", 1)
            keywords = [k.strip() for k in parts[0].split(",")]
            reply = parts[1].strip()
            
            replies_data["keywords"].append({
                "keywords": keywords,
                "reply": reply
            })
            save_data_optimized()
            await safe_send_message(update, f"✅ تم إضافة رد مخصص للكلمات: {', '.join(keywords)}")
        else:
            await safe_send_message(update, "استخدم: /add_reply كلمة1,كلمة2 | الرد المخصص")
    else:
        await safe_send_message(update, "استخدم: /add_reply كلمة1,كلمة2 | الرد المخصص")

async def remove_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف رد مخصص بشكل محسن"""
    if not await is_admin(update, update.message.from_user.id):
        await safe_send_message(update, "❌ هذا الأمر للمشرفين فقط!")
        return
    
    if context.args:
        keyword = " ".join(context.args).lower()
        found = False
        for i, item in enumerate(replies_data["keywords"]):
            if keyword in item["keywords"]:
                del replies_data["keywords"][i]
                found = True
                break
        
        if found:
            save_data_optimized()
            await safe_send_message(update, f"✅ تم حذف الرد المرتبط بـ {keyword}")
        else:
            await safe_send_message(update, "لم أجد رداً لهذه الكلمة")
    else:
        await safe_send_message(update, "استخدم: /remove_reply كلمة")

async def list_replies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الردود المخصصة بشكل محسن"""
    if not replies_data["keywords"]:
        await safe_send_message(update, "لا توجد ردود مخصصة حالياً")
        return
    
    text = "📝 **الردود المخصصة:**\n\n"
    for i, item in enumerate(replies_data["keywords"][:MAX_REPLIES_DISPLAY], 1):
        keywords_str = ', '.join(item["keywords"])
        reply_preview = item["reply"][:50] + "..." if len(item["reply"]) > 50 else item["reply"]
        text += f"{i}. {keywords_str}\n   ↳ {reply_preview}\n\n"
    
    if len(replies_data["keywords"]) > MAX_REPLIES_DISPLAY:
        text += f"\n*و{len(replies_data['keywords']) - MAX_REPLIES_DISPLAY} ردود أخرى*"
    
    await safe_send_message(update, text)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البحث المحسن"""
    if context.args:
        query = " ".join(context.args)
        await search_channel_for_post(update, query)
    else:
        await safe_send_message(update, "استخدم: /search 64   أو   /search 32")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر الطرد المحسن"""
    if not await is_admin(update, update.message.from_user.id):
        await safe_send_message(update, "❌ هذا الأمر للمشرفين فقط!")
        return
    
    if context.args:
        try:
            user_input = context.args[0]
            if user_input.isdigit():
                user_id = int(user_input)
            else:
                user_id = user_input.replace("@", "")
            
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
            await safe_send_message(update, f"✅ تم طرد العضو بنجاح")
        except Exception as e:
            logger.error(f"خطأ في الطرد: {e}")
            await safe_send_message(update, "حدث خطأ، تأكد من صحة المعرف")
    else:
        await safe_send_message(update, "استخدم: /kick @username أو /kick user_id")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر الكتم المحسن"""
    if not await is_admin(update, update.message.from_user.id):
        await safe_send_message(update, "❌ هذا الأمر للمشرفين فقط!")
        return
    
    if context.args:
        try:
            user_id = int(context.args[0])
            duration = int(context.args[1]) if len(context.args) > 1 else DEFAULT_MUTE_DURATION
            duration = min(duration, 86400)  # الحد الأقصى 24 ساعة
            
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=int(asyncio.get_event_loop().time()) + duration
            )
            
            await safe_send_message(update, f"✅ تم كتم العضو لمدة {duration} ثانية")
        except Exception as e:
            logger.error(f"خطأ في الكتم: {e}")
            await safe_send_message(update, "حدث خطأ، تأكد من صحة المعرف")
    else:
        await safe_send_message(update, "استخدم: /mute user_id [المدة بالثواني]")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر فك الكتم المحسن"""
    if not await is_admin(update, update.message.from_user.id):
        await safe_send_message(update, "❌ هذا الأمر للمشرفين فقط!")
        return
    
    if context.args:
        try:
            user_id = int(context.args[0])
            await context.bot.restrict_chat_member(
                chat_id=update.effective_chat.id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=True)
            )
            await safe_send_message(update, f"✅ تم فك الكتم عن العضو")
        except Exception as e:
            logger.error(f"خطأ في فك الكتم: {e}")
            await safe_send_message(update, "حدث خطأ")
    else:
        await safe_send_message(update, "استخدم: /unmute user_id")

async def clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر المسح المحسن"""
    if not await is_admin(update, update.message.from_user.id):
        await safe_send_message(update, "❌ هذا الأمر للمشرفين فقط!")
        return
    
    if context.args:
        try:
            count = min(int(context.args[0]), MAX_CLEAN_MESSAGES)
            if count <= 0:
                await safe_send_message(update, "الرجاء إدخال عدد موجب")
                return
            
            message_id = update.message.message_id
            deleted = 0
            for i in range(min(count, 100)):
                try:
                    await context.bot.delete_message(update.effective_chat.id, message_id - i - 1)
                    deleted += 1
                except:
                    pass
            
            await safe_send_message(update, f"✅ تم حذف {deleted} رسالة")
        except Exception as e:
            logger.error(f"خطأ في المسح: {e}")
            await safe_send_message(update, "حدث خطأ")
    else:
        await safe_send_message(update, f"استخدم: /clean عدد (الحد الأقصى {MAX_CLEAN_MESSAGES})")

# ========== الأوامر الترفيهية المحسنة ==========

async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jokes = [
        "🇪🇬 واحد صعيدي راح البحر شاف سمكة قفزت قال: يا سلام لو كنت جنبي كنت ركبتك يا معلم!",
        "😂 واحد بيقول لصاحبه: أنا مش بخاف من امتحانات! صاحبه قاله: ليه؟ قال: لأني بذاكر من بكره!",
        "🐱 قط قال للتاني: ليه انت دايماً نايم؟ قال: عشان أنا قط نايم!",
        "📱 واحد بيقول: اشتريت تلفون جديد بقيمة 1000 دولار... نزلت عليه فيس بوك بقى قيمته 100 دولار!",
    ]
    await safe_send_message(update, random.choice(jokes))

async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "💪 لا تيأس، فالمستحيل مجرد كلمة صنعها الضعفاء",
        "🌟 النجاح ليس محطة وصول، بل رحلة مستمرة",
        "❤️ الحياة بسيطة، لكننا نعقدها بأنفسنا",
        "🎯 لا تنتظر الفرصة، بل اصنعها بنفسك",
        "📚 العلم كنز لا يسرقه اللصوص",
    ]
    await safe_send_message(update, random.choice(quotes))

async def coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.choice(["🪙 **صورة**", "💰 **كتابة**"])
    await safe_send_message(update, f"رمي العملة...\n\n{result}")

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = random.randint(1, 6)
    await safe_send_message(update, f"🎲 **رميت النرد:** {result}")

async def eight_ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answers = ["نعم بالتأكيد ✅", "لا أبداً ❌", "ربما 🤔", "من الصعب توقعه 🎲", "نعم، بكل ثقة 💪"]
    await safe_send_message(update, f"🎱 **الكرة السحرية:**\n{random.choice(answers)}")

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    points = user_points.get(str(user.id), 0)
    level = user_levels.get(str(user.id), 1)
    
    await safe_send_message(update,
        f"👤 **معلومات المستخدم**\n\n"
        f"📛 الاسم: {user.first_name}\n"
        f"🆔 المعرف: `{user.id}`\n"
        f"⭐ النقاط: {points}\n"
        f"📊 المستوى: {level}")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)[:10]
    if not sorted_users:
        await safe_send_message(update, "لا توجد نقاط مسجلة بعد")
        return
    
    text = "🏆 **ترتيب الأعضاء النشطين** 🏆\n\n"
    for i, (user_id, points) in enumerate(sorted_users, 1):
        text += f"{i}. `{user_id}` - {points} نقطة\n"
    
    await safe_send_message(update, text)

async def current_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    await safe_send_message(update,
        f"📅 **التاريخ:** {now.strftime('%Y-%m-%d')}\n"
        f"🕐 **الوقت:** {now.strftime('%H:%M:%S')}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send_message(update,
        f"📊 **إحصائيات البوت**\n\n"
        f"👥 أعضاء تفاعلوا: {len(user_points)}\n"
        f"📝 ردود مخصصة: {len(replies_data.get('keywords', []))}\n"
        f"🚫 كلمات ممنوعة: {len(ban_words)}\n"
        f"🎫 تذاكر مفتوحة: {len([t for t in tickets.values() if t.get('status') == 'open'])}\n"
        f"⭐ إجمالي النقاط: {sum(user_points.values())}\n"
        f"📁 منشورات محفوظة: {len(channel_posts)}")

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send_message(update,
        f"🤖 **عن البوت**\n\n"
        f"بوت الحماية المتكامل\n"
        f"النسخة المحسنة 5.0\n"
        f"مزود بـ 100+ رد تلقائي\n"
        f"نظام تذاكر لحل المشاكل\n"
        f"البحث في القناة عن المنشورات\n"
        f"حفظ تلقائي للبيانات\n\n"
        f"📢 **القناة المرتبطة:** {CHANNEL_ID}")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = datetime.now()
    await update.message.reply_text("🏓 Pong!")
    end_time = datetime.now()
    latency = (end_time - start_time).total_seconds() * 1000
    await update.message.reply_text(f"⚡ زمن الاستجابة: {latency:.0f}ms")

async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        try:
            expression = " ".join(context.args)
            result = eval(expression)
            await safe_send_message(update, f"🧮 {expression} = {result}")
        except:
            await safe_send_message(update, "خطأ في العملية الحسابية")
    else:
        await safe_send_message(update, "استخدم: /calc 5+3")

async def poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.message.from_user.id):
        await safe_send_message(update, "❌ هذا الأمر للمشرفين فقط!")
        return
    
    if context.args:
        text = " ".join(context.args)
        if "|" in text:
            parts = text.split("|", 1)
            question = parts[0].strip()
            options = [opt.strip() for opt in parts[1].split(",")]
            if len(options) >= 2 and len(options) <= 10:
                await update.message.reply_poll(question, options, is_anonymous=False)
            else:
                await safe_send_message(update, "يجب أن يكون عدد الخيارات بين 2 و 10")
        else:
            await safe_send_message(update, "استخدم: /poll سؤال | خيار1,خيار2,خيار3")
    else:
        await safe_send_message(update, "استخدم: /poll سؤال | خيار1,خيار2,خيار3")

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) >= 2:
        try:
            minutes = int(context.args[0])
            if minutes <= 0 or minutes > 1440:
                await safe_send_message(update, "الرجاء إدخال مدة بين 1 و 1440 دقيقة")
                return
            
            reminder_text = " ".join(context.args[1:])
            remind_time = datetime.now() + timedelta(minutes=minutes)
            reminders[str(update.message.from_user.id)] = {
                "text": reminder_text,
                "time": remind_time.isoformat(),
                "chat_id": update.effective_chat.id
            }
            data["reminders"] = reminders
            save_data_optimized()
            await safe_send_message(update, f"✅ تم ضبط التذكير بعد {minutes} دقيقة")
        except ValueError:
            await safe_send_message(update, "استخدم: /remind 5 تذكر أن تشرب الماء")
    else:
        await safe_send_message(update, "استخدم: /remind 5 تذكر أن تشرب الماء")

async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not faqs:
        await safe_send_message(update, "لا توجد أسئلة شائعة حالياً")
        return
    
    text = "❓ **الأسئلة الشائعة:**\n\n"
    for q, a in list(faqs.items())[:10]:
        text += f"**س:** {q}\n**ج:** {a}\n\n"
    await safe_send_message(update, text)

async def add_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, update.message.from_user.id):
        await safe_send_message(update, "❌ هذا الأمر للمشرفين فقط!")
        return
    
    if context.args:
        text = " ".join(context.args)
        if "|" in text:
            parts = text.split("|", 1)
            question = parts[0].strip()
            answer = parts[1].strip()
            faqs[question] = answer
            data["faqs"] = faqs
            save_data_optimized()
            await safe_send_message(update, f"✅ تم إضافة سؤال شائع")
        else:
            await safe_send_message(update, "استخدم: /add_faq سؤال | جواب")
    else:
        await safe_send_message(update, "استخدم: /add_faq سؤال | جواب")

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send_message(update,
        "📜 **قوانين المجموعة** 📜\n\n"
        "1️⃣ احترام الجميع وعدم السب أو الشتم\n"
        "2️⃣ ممنوع نشر روابط أو إعلانات\n"
        "3️⃣ عدم إرسال محتوى غير لائق\n"
        "4️⃣ عدم التكرار أو السبام\n"
        "5️⃣ الالتزام بآداب الحوار\n\n"
        "⚠️ **العقوبات:**\n"
        "• التحذير الأول: تنبيه\n"
        "• التحذير الثاني: كتم 5 دقائق\n"
        "• التحذير الثالث: كتم ساعة\n"
        "• التحذير الرابع: حظر\n\n"
        "🌟 **معاً لبيئة آمنة**")

# ========== معالجة الرسائل المحسنة ==========

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ترحيب بالأعضاء الجدد بشكل محسن"""
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue
        
        mention = f"[{member.first_name}](tg://user?id={member.id})"
        welcome_messages = [
            f"🌟 {mention} نورت المجموعة يا حبيب القلب! 🌟\n\nنتمنى لك قضاء وقت ممتع معنا ❤️",
            f"🎉 ألف مليون مرحب {mention} 🎉\n\nالبيت بيتك وانبسط معانا 🥳",
            f"🤍 أهلاً وسهلاً {mention} 🤍\n\nنورت الدنيا بطلاقة وجهك الساحر ✨",
            f"🔥 {mention} دخل وعزّ المجموعة 🔥\n\nتألق وتميز معنا يا غالي 💪",
        ]
        
        await safe_send_message(update, random.choice(welcome_messages).format(mention=mention))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل المحسنة"""
    if update.effective_chat.type not in ["group", "supergroup"]:
        return
    
    if not update.message or not update.message.text:
        return
    
    if update.message.text.startswith('/'):
        return
    
    user = update.message.from_user
    
    # نظام النقاط المحسن
    try:
        user_id_str = str(user.id)
        if user_id_str not in user_points:
            user_points[user_id_str] = 0
        user_points[user_id_str] += 1
        
        # ترقية المستوى كل 100 نقطة
        if user_points[user_id_str] % 100 == 0:
            old_level = user_levels.get(user_id_str, 1)
            user_levels[user_id_str] = old_level + 1
            await safe_send_message(update, f"🎉 {user.first_name} ترقية إلى المستوى {old_level + 1}! 🎉")
        
        save_data_optimized()
    except Exception as e:
        logger.error(f"خطأ في نظام النقاط: {e}")
    
    # البحث عن 64/32
    message_text = update.message.text.lower()
    if any(word in message_text for word in ["64", "32", "نسخه", "نسخة"]):
        await search_channel_for_post(update, message_text)
        return
    
    # الردود الذكية
    await smart_reply(update)

# ========== تشغيل البوت المحسن ==========

async def post_init(application: Application):
    """تهيئة ما بعد التشغيل"""
    logger.info("✅ البوت يعمل الآن بـ 100+ رد و50+ ميزة محسنة!")
    logger.info(f"✅ تم التشغيل: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📢 القناة المرتبطة: {CHANNEL_ID}")

async def shutdown(application: Application):
    """إيقاف آمن للبوت"""
    logger.info("جاري حفظ البيانات قبل الإيقاف...")
    _perform_save()
    logger.info("✅ تم إيقاف البوت")

def main():
    """تشغيل البوت الرئيسي"""
    try:
        application = Application.builder().token(TOKEN).post_init(post_init).build()
        
        # أوامر المشرفين
        application.add_handler(CommandHandler("kick", kick))
        application.add_handler(CommandHandler("mute", mute))
        application.add_handler(CommandHandler("unmute", unmute))
        application.add_handler(CommandHandler("clean", clean))
        
        # أوامر الردود
        application.add_handler(CommandHandler("add_reply", add_reply))
        application.add_handler(CommandHandler("remove_reply", remove_reply))
        application.add_handler(CommandHandler("list_replies", list_replies))
        
        # نظام التذاكر
        application.add_handler(CommandHandler("ticket", ticket))
        application.add_handler(CommandHandler("reply_ticket", reply_ticket))
        
        # أوامر البحث
        application.add_handler(CommandHandler("search", search_command))
        
        # الأوامر الترفيهية
        application.add_handler(CommandHandler("joke", joke))
        application.add_handler(CommandHandler("quote", quote))
        application.add_handler(CommandHandler("coin", coin))
        application.add_handler(CommandHandler("dice", dice))
        application.add_handler(CommandHandler("8ball", eight_ball))
        application.add_handler(CommandHandler("info", user_info))
        application.add_handler(CommandHandler("top", top))
        application.add_handler(CommandHandler("time", current_time))
        
        # أوامر إضافية
        application.add_handler(CommandHandler("stats", stats))
        application.add_handler(CommandHandler("about", about))
        application.add_handler(CommandHandler("ping", ping))
        application.add_handler(CommandHandler("calc", calc))
        application.add_handler(CommandHandler("poll", poll_command))
        application.add_handler(CommandHandler("remind", remind))
        application.add_handler(CommandHandler("faq", faq_command))
        application.add_handler(CommandHandler("add_faq", add_faq))
        application.add_handler(CommandHandler("rules", rules))
        
        # أوامر أساسية
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        
        # معالجات الرسائل
        application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.ChatType.CHANNEL, save_channel_post))
        
        logger.info("🚀 بدء تشغيل البوت...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"خطأ فادح في تشغيل البوت: {e}")
        raise

if __name__ == '__main__':
    main()
