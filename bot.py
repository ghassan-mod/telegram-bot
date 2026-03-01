import os
import asyncio
import json
import tempfile
import random
import string
import logging
import hashlib
import base64
from datetime import datetime, timedelta
from telethon import TelegramClient, errors
from telethon.tl.types import DocumentAttributeFilename
from telethon.sessions import StringSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ==================== إعدادات التسجيل ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== متغيرات البيئة ====================
API_ID = 39458857
API_HASH = "3b62c284e0f6b6b0b16ba6d7b46a4a6f"
BOT_TOKEN = "8666815258:AAHrMUXt9GdlRkld5cLoOu3qFCPXRYZOQIQ"
ADMIN_ID = 1972494449
CHANNEL_USERNAME = "GSN_MOD"
SESSION_STRING = "BAJaGCkAJJKoci4eOFvNuC9h7YIRO1P1t9I-LfElqki5VLG6W7bAa6vY0fTwMWyvWxfj10jic5gDxBumhocdOQO9PIxKTRMdM1eo4ZNR5LwRyoBuBmIK25d6_jCsqwRR3tFRg9PnFPdf9rKF47TuQN87mRqjepwkIJQK6uNOt0oW3_qwq2Hl4_Iyf9QMBFSM6rr-P0onJ-sY9216AzG5ooY6PrQS4IZDVFimW8ePsPwmlXY1noXfKoJvY0mGSKqmFCl4iGfeR7GKUdBQK1r_gRujniiObSgeJap3xgcq422TfdmAKTDJE89iJYARhwQnLdMvCr2fmnsUsd3TTztUrO8a90KA1QAAAAB1keBxAA"
PHONE_NUMBER = ""  # اتركه فارغاً لأنك تستخدم Session String

if not CHANNEL_USERNAME.startswith('@'):
    CHANNEL_USERNAME = '@' + CHANNEL_USERNAME

# ==================== إعدادات المحادثة ====================
NAME, PHOTO, FILE, VERSION_CODE, DESCRIPTION, CODE_KEY, CODE_EXPIRY = range(7)
app_data = {}

# ==================== ملفات التخزين ====================
DOWNLOADS_FILE = "downloads_counter.json"
VERSION_COUNTER_FILE = "version_counter.json"
BOT_STATE_FILE = "bot_state.json"
CODES_FILE = "codes_database.json"
USERS_FILE = "users_database.json"
STATS_FILE = "stats_database.json"

# ==================== دوال المساعدة ====================
def load_json_file(filename, default=None):
    if default is None:
        default = {} if 'counter' not in filename else 0
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في تحميل {filename}: {e}")
        save_json_file(filename, default)
    return default

def save_json_file(filename, data):
    try:
        temp_file = f"{filename}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, filename)
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ {filename}: {e}")
        return False

def load_downloads():
    return load_json_file(DOWNLOADS_FILE, {})

def save_downloads(downloads):
    return save_json_file(DOWNLOADS_FILE, downloads)

def load_version_counter():
    data = load_json_file(VERSION_COUNTER_FILE, {'last_version': 0})
    return data.get('last_version', 0)

def save_version_counter(version):
    return save_json_file(VERSION_COUNTER_FILE, {'last_version': version})

def load_bot_state():
    return load_json_file(BOT_STATE_FILE, {
        'last_app_id': None, 
        'total_apps': 0, 
        'apps_list': [],
        'total_downloads': 0,
        'start_time': datetime.now().isoformat()
    })

def save_bot_state(state):
    return save_json_file(BOT_STATE_FILE, state)

def load_codes():
    return load_json_file(CODES_FILE, {'codes': {}, 'expiry_dates': {}})

def save_codes(codes_data):
    return save_json_file(CODES_FILE, codes_data)

def load_users():
    return load_json_file(USERS_FILE, {'users': {}, 'total_users': 0})

def save_users(users_data):
    return save_json_file(USERS_FILE, users_data)

def load_stats():
    return load_json_file(STATS_FILE, {
        'daily_downloads': {},
        'popular_apps': [],
        'total_requests': 0,
        'last_24h': 0
    })

def save_stats(stats_data):
    return save_json_file(STATS_FILE, stats_data)

def get_next_version():
    current = load_version_counter()
    next_version = current + 1
    save_version_counter(next_version)
    return f"V{next_version}"

def get_file_size(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size/1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size/(1024*1024):.1f} MB"
    else:
        return f"{size/(1024*1024*1024):.1f} GB"

def generate_code_key(version, app_name):
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    time_part = datetime.now().strftime('%H%M')
    code = f"{app_name[:3].upper()}-{random_part}-{time_part}"
    encoded = base64.b64encode(code.encode()).decode()[:12]
    return f"KEY-{encoded}"

def check_code_expiry(expiry_date):
    if not expiry_date:
        return True
    try:
        expiry = datetime.fromisoformat(expiry_date)
        return datetime.now() < expiry
    except:
        return True

def increment_download_count(app_id):
    downloads = load_downloads()
    stats = load_stats()
    
    if app_id in downloads:
        downloads[app_id]['downloads'] = downloads[app_id].get('downloads', 0) + 1
        save_downloads(downloads)
        
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in stats['daily_downloads']:
            stats['daily_downloads'][today] = 0
        stats['daily_downloads'][today] += 1
        stats['last_24h'] = stats['daily_downloads'].get(today, 0)
        save_stats(stats)
        
        return downloads[app_id]['downloads']
    return 0

def track_user(user_id, username, first_name):
    users = load_users()
    user_id_str = str(user_id)
    
    if user_id_str not in users['users']:
        users['users'][user_id_str] = {
            'username': username,
            'first_name': first_name,
            'first_seen': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'downloads_count': 0,
            'codes_requested': 0
        }
        users['total_users'] = len(users['users'])
    else:
        users['users'][user_id_str]['last_seen'] = datetime.now().isoformat()
        users['users'][user_id_str]['username'] = username
        users['users'][user_id_str]['first_name'] = first_name
    
    save_users(users)
    return users['total_users']

def increment_user_downloads(user_id):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str in users['users']:
        users['users'][user_id_str]['downloads_count'] += 1
        save_users(users)

# ==================== يوزربوت ====================
user_client = None

async def init_userbot():
    """تشغيل اليوزربوت مع Session String"""
    global user_client
    
    try:
        logger.info("🔄 جاري تشغيل اليوزربوت...")
        
        # استخدام Session String
        user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        
        # الاتصال بالخادم
        await user_client.connect()
        logger.info("✅ تم الاتصال بخادم تليجرام")
        
        # التحقق من تسجيل الدخول
        if not await user_client.is_user_authorized():
            logger.error("❌ Session String غير صالح!")
            return False
        
        # الحصول على معلومات المستخدم
        me = await user_client.get_me()
        logger.info(f"✅ اليوزربوت شغال كـ: {me.first_name} (ID: {me.id})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ فشل تشغيل اليوزربوت: {e}")
        user_client = None
        return False

async def ensure_userbot():
    """التأكد من تشغيل اليوزربوت"""
    global user_client
    
    try:
        if user_client is None:
            return await init_userbot()
        
        if not user_client.is_connected():
            await user_client.connect()
        
        # التحقق من الصلاحية
        try:
            await user_client.get_me()
            return True
        except:
            return await init_userbot()
            
    except Exception as e:
        logger.error(f"❌ خطأ في ensure_userbot: {e}")
        return False

# ==================== دوال البوت الرئيسية ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    total_users = track_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""✨ مرحباً بك في بوت GSN MOD! ✨

👤 {user.first_name}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📱 مميزات البوت:
• رفع التطبيقات بسهولة
• إنشاء أكواد خاصة
• إحصائيات دقيقة
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📊 عدد المستخدمين: {total_users}

🔰 أرسل اسم التطبيق للبدء"""
    
    await update.message.reply_text(welcome_text)
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    app_data[user_id] = {'name': update.message.text}
    await update.message.reply_text("✅ تم حفظ الاسم\n\n📸 أرسل صورة التطبيق الآن")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = await update.message.photo[-1].get_file()
    app_data[user_id]['photo'] = photo.file_id
    await update.message.reply_text("✅ تم حفظ الصورة\n\n📦 أرسل ملف التطبيق (APK)")
    return FILE

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document
    
    if not doc:
        await update.message.reply_text("❌ الرجاء إرسال ملف صالح")
        return FILE
    
    app_data[user_id]['file_id'] = doc.file_id
    app_data[user_id]['file_name'] = doc.file_name
    app_data[user_id]['file_size'] = get_file_size(doc.file_size)
    app_data[user_id]['raw_size'] = doc.file_size
    
    await update.message.reply_text("✅ تم حفظ الملف\n\n🔢 أرسل كود الإصدار (مثال: 1.0.0)")
    return VERSION_CODE

async def get_version_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    version = update.message.text
    
    if version.lower() in ['بدون', 'لا', 'none', '']:
        version = "1.0.0"
    
    app_data[user_id]['version_code'] = version
    
    keyboard = [
        [InlineKeyboardButton("✅ نعم، أضف كود", callback_data="code_yes")],
        [InlineKeyboardButton("❌ لا، بدون كود", callback_data="code_no")],
    ]
    
    await update.message.reply_text(
        "🔑 هل تريد إضافة كود خاص؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CODE_KEY

async def code_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == "code_yes":
        app_data[user_id]['has_code'] = True
        await query.edit_message_text("🔑 أرسل الكود الخاص")
        return CODE_KEY
    else:
        app_data[user_id]['has_code'] = False
        app_data[user_id]['code_key'] = None
        app_data[user_id]['expiry_days'] = None
        app_data[user_id]['version_num'] = get_next_version()
        app_data[user_id]['description'] = f"""🔥 {app_data[user_id]['name']} {app_data[user_id]['version_num']} 🔥

✅ تم رفع التطبيق بنجاح
📦 الحجم: {app_data[user_id]['file_size']}
📌 الإصدار: {app_data[user_id]['version_code']}

⚡️ حمل الآن واستمتع!"""
        
        await publish_app(update, context, user_id)
        return ConversationHandler.END

async def get_code_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text
    
    app_data[user_id]['code_key'] = code
    app_data[user_id]['has_code'] = True
    
    keyboard = [
        [InlineKeyboardButton("📅 30 يوم", callback_data="expiry_30")],
        [InlineKeyboardButton("📅 60 يوم", callback_data="expiry_60")],
        [InlineKeyboardButton("♾️ بدون انتهاء", callback_data="expiry_forever")]
    ]
    
    await update.message.reply_text(
        "⏳ اختر مدة الصلاحية",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CODE_EXPIRY

async def get_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == "expiry_forever":
        app_data[user_id]['expiry_days'] = None
    else:
        days = int(query.data.replace("expiry_", ""))
        app_data[user_id]['expiry_days'] = days
    
    app_data[user_id]['version_num'] = get_next_version()
    app_data[user_id]['description'] = f"""🔥 {app_data[user_id]['name']} {app_data[user_id]['version_num']} 🔥

🔑 الكود: {app_data[user_id]['code_key']}
✅ تم رفع التطبيق بنجاح
📦 الحجم: {app_data[user_id]['file_size']}
📌 الإصدار: {app_data[user_id]['version_code']}

⚡️ حمل الآن واستمتع!"""
    
    await query.edit_message_text("✅ تم تحديد المدة، جاري النشر...")
    await publish_app(update, context, user_id)
    return ConversationHandler.END

async def publish_app(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """نشر التطبيق في القناة"""
    data = app_data[user_id]
    version_num = data['version_num']
    app_id = f"app_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # حفظ الكود إذا وجد
    if data.get('has_code', False) and data.get('code_key'):
        codes_data = load_codes()
        codes_data['codes'][version_num] = {
            'key': data['code_key'],
            'app_name': data['name'],
            'version': version_num,
            'created_at': datetime.now().isoformat()
        }
        
        if data.get('expiry_days'):
            expiry_date = (datetime.now() + timedelta(days=data['expiry_days'])).isoformat()
            codes_data['expiry_dates'][version_num] = expiry_date
        
        save_codes(codes_data)
    
    # حفظ التطبيق
    downloads = load_downloads()
    downloads[app_id] = {
        'id': app_id,
        'name': data['name'],
        'version': version_num,
        'version_code': data['version_code'],
        'file_id': data['file_id'],
        'file_name': data['file_name'],
        'file_size': data['file_size'],
        'raw_size': data.get('raw_size', 0),
        'description': data['description'],
        'downloads': 0,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'uploader_id': user_id,
        'has_code': data.get('has_code', False),
        'code_key': data.get('code_key') if data.get('has_code', False) else None
    }
    save_downloads(downloads)
    
    # تحديث حالة البوت
    bot_state = load_bot_state()
    if 'apps_list' not in bot_state:
        bot_state['apps_list'] = []
    
    bot_state['apps_list'].insert(0, {
        'app_id': app_id,
        'name': data['name'],
        'version': version_num,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'downloads': 0
    })
    
    if len(bot_state['apps_list']) > 100:
        bot_state['apps_list'] = bot_state['apps_list'][:100]
    
    bot_state['total_apps'] = len(downloads)
    bot_state['total_downloads'] = sum(a.get('downloads', 0) for a in downloads.values())
    save_bot_state(bot_state)
    
    # تجهيز الكيبورد
    keyboard_buttons = [
        [
            InlineKeyboardButton(f"📥 تحميل", callback_data=f"download_{app_id}"),
            InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info_{app_id}")
        ]
    ]
    
    if data.get('has_code', False) and data.get('code_key'):
        keyboard_buttons[0].insert(1, InlineKeyboardButton("🔑 الكود", callback_data=f"code_{app_id}"))
    
    keyboard_buttons.append([
        InlineKeyboardButton("📊 الإحصائيات", callback_data="global_stats"),
        InlineKeyboardButton("📱 القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
    ])
    
    # إرسال للقناة
    await context.bot.send_photo(
        CHANNEL_USERNAME,
        data['photo'],
        caption=data['description'],
        reply_markup=InlineKeyboardMarkup(keyboard_buttons)
    )
    
    # إرسال تأكيد للمستخدم
    confirm_text = f"""✅ تم النشر بنجاح!

📱 التطبيق: {data['name']}
📌 الإصدار: {version_num}
📢 القناة: {CHANNEL_USERNAME}"""

    if data.get('has_code', False) and data.get('code_key'):
        confirm_text += f"\n🔑 الكود: {data['code_key']}"
    
    await context.bot.send_message(
        chat_id=user_id,
        text=confirm_text
    )
    
    del app_data[user_id]

# ==================== معالجة الأزرار ====================
async def download_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر التحميل"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("📦 جاري التحميل...")
    
    # تتبع المستخدم
    track_user(user_id, query.from_user.username, query.from_user.first_name)
    
    app_id = query.data.replace("download_", "")
    downloads = load_downloads()
    app = downloads.get(app_id)
    
    if not app:
        await query.edit_message_text("❌ التطبيق غير موجود")
        return
    
    # إرسال رسالة الحالة
    status_msg = await context.bot.send_message(
        chat_id=user_id,
        text=f"📦 جاري تجهيز {app['name']}\n\n⏳ الرجاء الانتظار..."
    )
    
    try:
        # التأكد من تشغيل اليوزربوت
        userbot_ok = await ensure_userbot()
        if not userbot_ok:
            await status_msg.edit_text(
                "❌ عذراً، البوت تحت الصيانة\n\n"
                "يرجى المحاولة لاحقاً"
            )
            return
        
        # تحميل الملف
        await status_msg.edit_text("📥 جاري تحميل الملف...")
        file = await context.bot.get_file(app['file_id'])
        
        # إنشاء ملف مؤقت
        with tempfile.NamedTemporaryFile(delete=False, suffix='.apk') as tmp:
            path = tmp.name
        
        # تحميل الملف
        await file.download_to_drive(path)
        
        # إرسال الملف
        await status_msg.edit_text("📤 جاري الإرسال إلى الخاص...")
        
        caption = f"""✅ {app['name']} {app['version']}

📥 تم التحميل بنجاح
⚡️ استمتع بالتجربة
        
📊 {app['file_size']} | الإصدار: {app['version_code']}"""
        
        await user_client.send_file(
            user_id, 
            path, 
            caption=caption,
            attributes=[DocumentAttributeFilename(app['file_name'])]
        )
        
        # تنظيف
        os.remove(path)
        
        # تحديث العداد
        new_count = increment_download_count(app_id)
        increment_user_downloads(user_id)
        
        await status_msg.edit_text(
            f"✅ تم الإرسال بنجاح!\n\n"
            f"📱 {app['name']}\n"
            f"📥 عدد التحميلات: {new_count}"
        )
        
    except errors.FloodWaitError as e:
        wait_time = e.seconds
        await status_msg.edit_text(
            f"⚠️ تقييد من تليجرام\n\n"
            f"الرجاء الانتظار {wait_time // 60} دقيقة"
        )
        
    except Exception as e:
        logger.error(f"❌ خطأ في التحميل: {e}")
        await status_msg.edit_text(
            f"❌ حدث خطأ: {str(e)[:100]}"
        )
        
        if 'path' in locals() and os.path.exists(path):
            os.remove(path)

async def code_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر الكود"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("🔑 جاري تجهيز الكود...")
    
    app_id = query.data.replace("code_", "")
    downloads = load_downloads()
    app = downloads.get(app_id)
    
    if not app or not app.get('code_key'):
        await query.edit_message_text("❌ الكود غير موجود")
        return
    
    # إرسال الكود في الخاص
    await context.bot.send_message(
        chat_id=user_id,
        text=f"""🔑 كود {app['version']}

{app['code_key']}

📱 التطبيق: {app['name']}"""
    )
    
    await query.edit_message_text("✅ تم إرسال الكود إلى الخاص")

async def info_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات التطبيق"""
    query = update.callback_query
    await query.answer()
    
    app_id = query.data.replace("info_", "")
    downloads = load_downloads()
    app = downloads.get(app_id)
    
    if not app:
        await query.edit_message_text("❌ التطبيق غير موجود")
        return
    
    info_text = f"""ℹ️ معلومات التطبيق

📱 الاسم: {app['name']}
📌 الإصدار: {app['version']}
🔢 كود الإصدار: {app['version_code']}
📦 الحجم: {app['file_size']}
📅 تاريخ الرفع: {app['date']}
📥 مرات التحميل: {app.get('downloads', 0)}"""
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"back_{app_id}")]]
    await query.edit_message_caption(
        caption=info_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرجوع للوصف الرئيسي"""
    query = update.callback_query
    await query.answer()
    
    app_id = query.data.replace("back_", "")
    downloads = load_downloads()
    app = downloads.get(app_id)
    
    if app:
        keyboard_buttons = [
            [
                InlineKeyboardButton(f"📥 تحميل ({app.get('downloads', 0)})", callback_data=f"download_{app_id}"),
                InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info_{app_id}")
            ]
        ]
        if app.get('has_code', False) and app.get('code_key'):
            keyboard_buttons[0].insert(1, InlineKeyboardButton("🔑 الكود", callback_data=f"code_{app_id}"))
        
        keyboard_buttons.append([
            InlineKeyboardButton("📊 الإحصائيات", callback_data="global_stats"),
            InlineKeyboardButton("📱 القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
        ])
        
        await query.edit_message_caption(
            caption=app['description'],
            reply_markup=InlineKeyboardMarkup(keyboard_buttons)
        )

async def global_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإحصائيات العامة"""
    query = update.callback_query
    await query.answer()
    
    downloads = load_downloads()
    users = load_users()
    
    total_apps = len(downloads)
    total_downloads = sum(a.get('downloads', 0) for a in downloads.values())
    total_users = users.get('total_users', 0)
    
    stats_text = f"""📊 إحصائيات البوت

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📱 التطبيقات: {total_apps}
👥 المستخدمين: {total_users}
📥 إجمالي التحميلات: {total_downloads}"""
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
    await query.edit_message_caption(
        caption=stats_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للرسالة الرئيسية"""
    query = update.callback_query
    await query.answer()
    await query.message.delete()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

# ==================== أوامر المشرف ====================
async def admin_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    status_msg = await update.message.reply_text("🔍 جاري الفحص...")
    
    try:
        userbot_ok = await ensure_userbot()
        
        downloads = load_downloads()
        users = load_users()
        
        status_text = f"""📊 حالة البوت

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🤖 البوت: ✅ يعمل
👤 اليوزربوت: {'✅ يعمل' if userbot_ok else '❌ لا يعمل'}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📱 التطبيقات: {len(downloads)}
👥 المستخدمين: {users.get('total_users', 0)}"""
        
        await status_msg.edit_text(status_text)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ خطأ: {str(e)}")

# ==================== التشغيل الرئيسي ====================
async def main():
    """تشغيل البوت"""
    try:
        # تشغيل اليوزربوت
        logger.info("🚀 جاري تشغيل اليوزربوت...")
        userbot_ok = await init_userbot()
        
        if userbot_ok:
            logger.info("✅ اليوزربوت يعمل بنجاح")
        else:
            logger.warning("⚠️ اليوزربوت لا يعمل، بعض الميزات قد لا تعمل")
        
        # تشغيل البوت
        logger.info("🤖 جاري تشغيل البوت...")
        app = Application.builder().token(BOT_TOKEN).build()
        
        # محادثة رفع التطبيقات
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
                FILE: [MessageHandler(filters.Document.ALL, get_file)],
                VERSION_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_version_code)],
                CODE_KEY: [
                    CallbackQueryHandler(code_decision, pattern='^code_'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_code_key)
                ],
                CODE_EXPIRY: [CallbackQueryHandler(get_expiry, pattern='^expiry_')],
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        app.add_handler(conv_handler)
        
        # أزرار التفاعل
        app.add_handler(CallbackQueryHandler(download_button, pattern='^download_'))
        app.add_handler(CallbackQueryHandler(code_button, pattern='^code_'))
        app.add_handler(CallbackQueryHandler(info_button, pattern='^info_'))
        app.add_handler(CallbackQueryHandler(back_button, pattern='^back_'))
        app.add_handler(CallbackQueryHandler(global_stats, pattern='^global_stats$'))
        app.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))
        
        # أوامر المشرف
        app.add_handler(CommandHandler('test', admin_test))
        
        logger.info(f"✅ البوت شغال على @{CHANNEL_USERNAME}")
        await app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل البوت: {e}")

if __name__ == '__main__':
    asyncio.run(main())
