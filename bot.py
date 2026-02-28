import os
import asyncio
import json
import tempfile
import random
import string
from datetime import datetime, timedelta
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import logging

# إعدادات التسجيل المتقدمة
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# متغيرات البيئة
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PHONE_NUMBER = os.environ.get('PHONE_NUMBER')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME')
SESSION_STRING = os.environ.get('SESSION_STRING', '')
BACKUP_CHANNEL = os.environ.get('BACKUP_CHANNEL', '')  # قناة احتياطية للنسخ الاحتياطي

if not CHANNEL_USERNAME.startswith('@'):
    CHANNEL_USERNAME = '@' + CHANNEL_USERNAME
if BACKUP_CHANNEL and not BACKUP_CHANNEL.startswith('@'):
    BACKUP_CHANNEL = '@' + BACKUP_CHANNEL

# إعدادات البوت
NAME, PHOTO, FILE, VERSION_CODE, DESCRIPTION, CODE_KEY, CODE_EXPIRY = range(7)
app_data = {}

# ملفات التخزين
DOWNLOADS_FILE = "downloads_counter.json"
VERSION_COUNTER_FILE = "version_counter.json"
BOT_STATE_FILE = "bot_state.json"
CODES_FILE = "codes_database.json"
USERS_FILE = "users_database.json"
STATS_FILE = "stats_database.json"
BACKUP_FILE = "backup_database.json"

# التأكد من وجود مجلد temp
temp_dir = tempfile.gettempdir()
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# ==================== دوال المساعدة المتقدمة ====================

def load_json_file(filename, default=None):
    """تحميل ملف JSON مع معالجة الأخطاء"""
    if default is None:
        default = {} if 'counter' not in filename else 0
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"❌ ملف {filename} تالف، جاري إنشاء ملف جديد: {e}")
        # عمل نسخة احتياطية من الملف التالف
        if os.path.exists(filename):
            backup_name = f"{filename}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(filename, backup_name)
            logger.info(f"💾 تم حفظ نسخة احتياطية من الملف التالف: {backup_name}")
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل {filename}: {e}")
    
    # إنشاء ملف جديد بالقيم الافتراضية
    save_json_file(filename, default)
    return default

def save_json_file(filename, data):
    """حفظ ملف JSON مع التأكد من سلامة البيانات"""
    try:
        # حفظ مؤقت ثم إعادة التسمية لضمان سلامة الملف
        temp_file = f"{filename}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, filename)
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ {filename}: {e}")
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
        'start_time': datetime.now().isoformat(),
        'last_backup': None
    })

def save_bot_state(state):
    return save_json_file(BOT_STATE_FILE, state)

def load_codes():
    return load_json_file(CODES_FILE, {'codes': {}, 'expiry_dates': {}, 'used_codes': {}})

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
    """الحصول على الإصدار التالي"""
    current = load_version_counter()
    next_version = current + 1
    save_version_counter(next_version)
    return f"V{next_version}"

def get_file_size(size):
    """تحويل حجم الملف إلى صيغة مقروءة"""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size/1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size/(1024*1024):.1f} MB"
    else:
        return f"{size/(1024*1024*1024):.1f} GB"

def generate_code_key(version, app_name):
    """توليد كود عشوائي فريد"""
    import hashlib
    import base64
    
    # توليد كود فريد
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    time_part = datetime.now().strftime('%H%M')
    code = f"{app_name[:3].upper()}-{random_part}-{time_part}"
    
    # تشفير الكود
    encoded = base64.b64encode(code.encode()).decode()[:12]
    return f"KEY-{encoded}"

def check_code_expiry(expiry_date):
    """التحقق من صلاحية الكود"""
    if not expiry_date:
        return True
    try:
        expiry = datetime.fromisoformat(expiry_date)
        return datetime.now() < expiry
    except:
        return True

def get_code_status(expiry_date):
    """الحصول على حالة الكود مع تنسيق جميل"""
    if not expiry_date:
        return "✅ **دائم (بدون انتهاء)**"
    try:
        expiry = datetime.fromisoformat(expiry_date)
        remaining = expiry - datetime.now()
        if remaining.days < 0:
            return "❌ **منتهي الصلاحية**"
        elif remaining.days == 0:
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            return f"⚠️ **ينتهي اليوم** (بعد {hours} ساعة و {minutes} دقيقة)"
        elif remaining.days < 7:
            return f"⏳ **متبقي {remaining.days} يوم**"
        else:
            weeks = remaining.days // 7
            days = remaining.days % 7
            return f"📅 **متبقي {weeks} أسبوع و {days} يوم**"
    except:
        return "✅ **صالح**"

def increment_download_count(app_id):
    """زيادة عداد التحميلات مع تحديث الإحصائيات"""
    downloads = load_downloads()
    stats = load_stats()
    
    if app_id in downloads:
        downloads[app_id]['downloads'] += 1
        save_downloads(downloads)
        
        # تحديث الإحصائيات اليومية
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in stats['daily_downloads']:
            stats['daily_downloads'][today] = 0
        stats['daily_downloads'][today] += 1
        stats['last_24h'] = stats['daily_downloads'].get(today, 0)
        
        # تحديث قائمة التطبيقات الأكثر تحميلاً
        app_stats = {
            'app_id': app_id,
            'name': downloads[app_id]['name'],
            'downloads': downloads[app_id]['downloads']
        }
        
        # تحديث القائمة
        popular = stats['popular_apps']
        existing = next((i for i, a in enumerate(popular) if a['app_id'] == app_id), None)
        if existing is not None:
            popular[existing] = app_stats
        else:
            popular.append(app_stats)
        
        # ترتيب تنازلي
        stats['popular_apps'] = sorted(popular, key=lambda x: x['downloads'], reverse=True)[:10]
        save_stats(stats)
        
        return downloads[app_id]['downloads']
    return 0

def track_user(user_id, username, first_name):
    """تتبع المستخدمين"""
    users = load_users()
    
    if str(user_id) not in users['users']:
        users['users'][str(user_id)] = {
            'username': username,
            'first_name': first_name,
            'first_seen': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'downloads_count': 0,
            'codes_requested': 0
        }
        users['total_users'] = len(users['users'])
    else:
        users['users'][str(user_id)]['last_seen'] = datetime.now().isoformat()
        users['users'][str(user_id)]['username'] = username
        users['users'][str(user_id)]['first_name'] = first_name
    
    save_users(users)
    return users['total_users']

def increment_user_downloads(user_id):
    """زيادة عداد تحميلات المستخدم"""
    users = load_users()
    if str(user_id) in users['users']:
        users['users'][str(user_id)]['downloads_count'] += 1
        save_users(users)

def increment_user_codes(user_id):
    """زيادة عداد طلبات الكود للمستخدم"""
    users = load_users()
    if str(user_id) in users['users']:
        users['users'][str(user_id)]['codes_requested'] += 1
        save_users(users)

async def create_backup():
    """إنشاء نسخة احتياطية من جميع البيانات"""
    try:
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'downloads': load_downloads(),
            'version_counter': load_version_counter(),
            'bot_state': load_bot_state(),
            'codes': load_codes(),
            'users': load_users(),
            'stats': load_stats()
        }
        
        # حفظ محلياً
        save_json_file(BACKUP_FILE, backup_data)
        
        # إرسال للقناة الاحتياطية إذا وجدت
        if BACKUP_CHANNEL and user_client:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', encoding='utf-8', delete=False) as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
                backup_path = f.name
            
            await user_client.send_file(
                BACKUP_CHANNEL,
                backup_path,
                caption=f"📦 **نسخة احتياطية**\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode='Markdown'
            )
            os.remove(backup_path)
        
        # تحديث آخر نسخة احتياطية
        state = load_bot_state()
        state['last_backup'] = datetime.now().isoformat()
        save_bot_state(state)
        
        logger.info("✅ تم إنشاء نسخة احتياطية بنجاح")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إنشاء النسخة الاحتياطية: {e}")
        return False

# ==================== دوال اليوزربوت المتقدمة ====================

user_client = None
userbot_status = {'connected': False, 'last_check': None, 'errors': 0}

async def init_userbot():
    """تشغيل اليوزربوت مع محاولات متعددة"""
    global user_client, userbot_status
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            logger.info(f"🔄 محاولة تشغيل اليوزربوت ({attempt + 1}/{max_attempts})...")
            
            # استخدام Session String إذا كان موجود
            if SESSION_STRING:
                logger.info("📱 استخدام Session String للاتصال")
                user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
            else:
                logger.info("📱 استخدام رقم الهاتف للاتصال")
                user_client = TelegramClient('user_session', API_ID, API_HASH)
            
            # الاتصال بالخادم
            await user_client.connect()
            logger.info("✅ تم الاتصال بخادم تليجرام")
            
            # التحقق من تسجيل الدخول
            if not await user_client.is_user_authorized():
                logger.info("📱 جاري تسجيل الدخول برقم الهاتف...")
                await user_client.start(phone=PHONE_NUMBER)
                
                # حفظ Session String
                if not SESSION_STRING:
                    session_str = StringSession.save(user_client.session)
                    logger.info(f"🔑 SESSION_STRING={session_str}")
                    logger.info("💡 احفظ هذا الكود في متغير SESSION_STRING")
            
            # الحصول على معلومات المستخدم
            me = await user_client.get_me()
            logger.info(f"✅ اليوزربوت شغال كـ: {me.first_name} (ID: {me.id})")
            
            userbot_status['connected'] = True
            userbot_status['last_check'] = datetime.now().isoformat()
            userbot_status['errors'] = 0
            
            # إنشاء نسخة احتياطية تلقائية
            if attempt == 0:  # فقط في المحاولة الأولى
                asyncio.create_task(create_backup())
            
            return True
            
        except Exception as e:
            logger.error(f"❌ فشل المحاولة {attempt + 1}: {e}")
            userbot_status['errors'] += 1
            
            if user_client:
                await user_client.disconnect()
                user_client = None
            
            if attempt < max_attempts - 1:
                wait_time = 5 * (attempt + 1)
                logger.info(f"⏳ انتظار {wait_time} ثواني قبل المحاولة التالية...")
                await asyncio.sleep(wait_time)
    
    userbot_status['connected'] = False
    return False

async def ensure_userbot():
    """التأكد من تشغيل اليوزربوت"""
    global user_client, userbot_status
    
    try:
        if user_client is None:
            return await init_userbot()
        
        if not user_client.is_connected():
            logger.info("🔄 جاري إعادة الاتصال...")
            await user_client.connect()
        
        # التحقق من الصلاحية
        try:
            await user_client.get_me()
            userbot_status['connected'] = True
            userbot_status['last_check'] = datetime.now().isoformat()
            return True
        except Exception as e:
            logger.warning(f"⚠️ اليوزربوت غير صالح: {e}")
            userbot_status['connected'] = False
            userbot_status['errors'] += 1
            
            # محاولة إعادة التشغيل إذا كثرت الأخطاء
            if userbot_status['errors'] > 5:
                logger.warning("🔄 كثرة الأخطاء، جاري إعادة تشغيل اليوزربوت...")
                await user_client.disconnect()
                user_client = None
                return await init_userbot()
            
            return False
            
    except Exception as e:
        logger.error(f"❌ خطأ في ensure_userbot: {e}")
        return False

async def download_with_progress(user_id, file, path, status_msg):
    """تحميل الملف مع عرض التقدم"""
    try:
        file_size = file.file_size
        await status_msg.edit_text(f"📥 جاري التحميل... 0%")
        
        # دالة تحديث التقدم
        async def progress_callback(current, total):
            if total > 0:
                percent = (current / total) * 100
                if percent % 10 == 0:  # تحديث كل 10%
                    await status_msg.edit_text(f"📥 جاري التحميل... {percent:.0f}%")
        
        await file.download_to_drive(path, progress_callback=progress_callback)
        await status_msg.edit_text("✅ تم التحميل بنجاح!")
        return True
        
    except Exception as e:
        logger.error(f"❌ فشل التحميل: {e}")
        await status_msg.edit_text("❌ فشل التحميل")
        return False

# ==================== دوال البوت الرئيسية ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية المحادثة"""
    user = update.effective_user
    total_users = track_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""✨ **مرحباً بك في بوت GSN MOD المتطور!** ✨

👤 {user.first_name}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📱 **مميزات البوت:**
• رفع التطبيقات بسهولة
• إنشاء أكواد خاصة
• إحصائيات دقيقة
• نسخ احتياطي تلقائي
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📊 عدد المستخدمين: {total_users}

🔰 **أرسل اسم التطبيق للبدء**"""
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام اسم التطبيق"""
    user_id = update.effective_user.id
    app_data[user_id] = {'name': update.message.text}
    
    await update.message.reply_text(
        "✅ **تم حفظ الاسم**\n\n"
        "📸 أرسل **صورة التطبيق** الآن",
        parse_mode='Markdown'
    )
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام صورة التطبيق"""
    user_id = update.effective_user.id
    photo = await update.message.photo[-1].get_file()
    app_data[user_id]['photo'] = photo.file_id
    
    await update.message.reply_text(
        "✅ **تم حفظ الصورة**\n\n"
        "📦 أرسل **ملف التطبيق** (APK)",
        parse_mode='Markdown'
    )
    return FILE

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام ملف التطبيق"""
    user_id = update.effective_user.id
    doc = update.message.document
    
    if not doc:
        await update.message.reply_text(
            "❌ **خطأ**\n"
            "الرجاء إرسال ملف صالح",
            parse_mode='Markdown'
        )
        return FILE
    
    # التحقق من نوع الملف
    if not doc.file_name.endswith('.apk'):
        keyboard = [[InlineKeyboardButton("⚠️ متابعة على مسؤوليتي", callback_data="continue_anyway")]]
        await update.message.reply_text(
            "⚠️ **تحذير**\n"
            "الملف ليس بصيغة APK. هل تريد المتابعة؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        # سنكمل على أي حال
    
    app_data[user_id]['file_id'] = doc.file_id
    app_data[user_id]['file_name'] = doc.file_name
    app_data[user_id]['file_size'] = get_file_size(doc.file_size)
    app_data[user_id]['raw_size'] = doc.file_size
    
    await update.message.reply_text(
        "✅ **تم حفظ الملف**\n\n"
        "🔢 أرسل **كود الإصدار** (مثال: 1.0.0)",
        parse_mode='Markdown'
    )
    return VERSION_CODE

async def continue_anyway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """متابعة رغم تحذير الصيغة"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✅ **تم التجاهل**\n\n"
        "🔢 أرسل **كود الإصدار** (مثال: 1.0.0)",
        parse_mode='Markdown'
    )
    return VERSION_CODE

async def get_version_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام كود الإصدار"""
    user_id = update.effective_user.id
    version = update.message.text
    
    if version.lower() in ['بدون', 'لا', 'none', '']:
        version = "1.0.0"
    
    app_data[user_id]['version_code'] = version
    
    # سؤال عن إضافة كود
    keyboard = [
        [InlineKeyboardButton("✅ نعم، أضف كود", callback_data="code_yes")],
        [InlineKeyboardButton("❌ لا، بدون كود", callback_data="code_no")],
        [InlineKeyboardButton("🎲 توليد كود عشوائي", callback_data="code_random")]
    ]
    
    await update.message.reply_text(
        "🔑 **هل تريد إضافة كود خاص؟**\n\n"
        "الكود يمكن للمستخدمين طلبه في المجموعة",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CODE_KEY

async def code_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اتخاذ قرار بشأن الكود"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id not in app_data:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل /start مرة أخرى")
        return ConversationHandler.END
    
    if query.data == "code_random":
        # توليد كود عشوائي
        data = app_data[user_id]
        version_num = get_next_version()  # مؤقت
        random_code = generate_code_key(version_num, data['name'])
        app_data[user_id]['code_key'] = random_code
        app_data[user_id]['has_code'] = True
        
        await query.edit_message_text(
            f"✅ **تم توليد كود عشوائي**\n\n"
            f"🔑 `{random_code}`\n\n"
            f"الآن اختر مدة الصلاحية:",
            parse_mode='Markdown'
        )
        
        # عرض خيارات الصلاحية
        keyboard = [
            [InlineKeyboardButton("📅 30 يوم", callback_data="expiry_30")],
            [InlineKeyboardButton("📅 60 يوم", callback_data="expiry_60")],
            [InlineKeyboardButton("📅 90 يوم", callback_data="expiry_90")],
            [InlineKeyboardButton("♾️ بدون انتهاء", callback_data="expiry_forever")]
        ]
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        return CODE_EXPIRY
        
    elif query.data == "code_yes":
        app_data[user_id]['has_code'] = True
        await query.edit_message_text(
            "🔑 **أرسل الكود الخاص**\n\n"
            "مثال: GSN-PRO-2024\n\n"
            "يمكنك كتابة أي كود تريده",
            parse_mode='Markdown'
        )
        return CODE_KEY
    else:
        app_data[user_id]['has_code'] = False
        app_data[user_id]['code_key'] = None
        app_data[user_id]['expiry_days'] = None
        await show_description_options(update, context, user_id)
        return DESCRIPTION

async def get_code_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام الكود من المستخدم"""
    user_id = update.effective_user.id
    code = update.message.text
    
    app_data[user_id]['code_key'] = code
    app_data[user_id]['has_code'] = True
    
    keyboard = [
        [InlineKeyboardButton("📅 30 يوم", callback_data="expiry_30")],
        [InlineKeyboardButton("📅 60 يوم", callback_data="expiry_60")],
        [InlineKeyboardButton("📅 90 يوم", callback_data="expiry_90")],
        [InlineKeyboardButton("♾️ بدون انتهاء", callback_data="expiry_forever")]
    ]
    
    await update.message.reply_text(
        "⏳ **اختر مدة الصلاحية**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CODE_EXPIRY

async def get_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تحديد مدة الصلاحية"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id not in app_data:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل /start مرة أخرى")
        return ConversationHandler.END
    
    if query.data == "expiry_forever":
        app_data[user_id]['expiry_days'] = None
    else:
        days = int(query.data.replace("expiry_", ""))
        app_data[user_id]['expiry_days'] = days
    
    await query.edit_message_text("✅ تم تحديد المدة، جاري تجهيز الوصف...")
    await show_description_options(update, context, user_id)
    return DESCRIPTION

async def show_description_options(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """عرض خيارات الوصف"""
    keyboard = [
        [InlineKeyboardButton("🔥 وصف قوي", callback_data="desc_strong")],
        [InlineKeyboardButton("✨ وصف احترافي", callback_data="desc_professional")],
        [InlineKeyboardButton("⚡️ وصف خرافي", callback_data="desc_amazing")],
        [InlineKeyboardButton("🎯 وصف للمحترفين", callback_data="desc_pro")],
        [InlineKeyboardButton("🌟 وصف VIP", callback_data="desc_vip")],
        [InlineKeyboardButton("📝 كتابة وصف مخصص", callback_data="desc_custom")]
    ]
    
    text = "📝 **اختر نوع الوصف**\n\nاختر وصفاً جاهزاً أو اكتب وصفتك الخاصة"
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def description_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الوصف"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id not in app_data:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل /start مرة أخرى")
        return ConversationHandler.END
    
    desc_type = query.data.replace("desc_", "")
    
    if desc_type == "custom":
        await query.edit_message_text(
            "📝 **اكتب الوصف الخاص بك**\n\n"
            "يمكنك استخدام Markdown للتنسيق",
            parse_mode='Markdown'
        )
        return DESCRIPTION
    
    data = app_data[user_id]
    version_num = get_next_version()
    
    # أوصاف متنوعة وجذابة
    descriptions = {
        "strong": f"""🔥 **{data['name']} {version_num} - مخصوص للأجهزة الضعيفة!** 🔥

⚡️ لو جهازك ضعيف... ولا يهمك!
النسخة دي معمولة عشان تطيرك في اللعبة بدون لاج ولا تهنيج! 🚀

🎮 **ثبات أكثر - لاج أقل - أداء خرافي**
سيطر على اللعبة يا زعيم 💥😈

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📦 **المعلومات:**
• الحجم: {data['file_size']}
• الإصدار: {version_num}
• الكود: {data['version_code']}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

✅ **مضمونة 100%** - مجربة ومشغالة
⚡️ **تحديث مستمر** - أحدث إصدار""",
        
        "professional": f"""✨ **{data['name']} {version_num} - الإصدار الذهبي!** ✨

🚀 **أسرع نسخة على الإطلاق**
🎯 **بدون تهنيج** حتى على أضعف الأجهزة

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
💪 **المميزات:**
✓ ثبات في FPS
✓ استهلاك أقل للرام
✓ بطارية تدوم أطول
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

📊 {data['file_size']} | {version_num} | {data['version_code']}
🔥 **تجربة أسطورية في انتظارك**""",
        
        "amazing": f"""⚡️ **{data['name']} {version_num} - النسخة الخرافية** ⚡️

🎯 للمحترفين فقط
🏆 أفضل أداء - أقل لاج

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
💎 **لماذا هذه النسخة؟**
✅ تشتغل على كل الأجهزة
✅ تحديثات مستمرة
✅ دعم فني 24/7
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

📥 تحميل مباشر وآمن
📊 {data['file_size']} | {version_num}
🌟 ثقة الآلاف من المستخدمين""",
        
        "pro": f"""🎯 **{data['name']} {version_num} - للمحترفين** 🎯

🔥 أداء أسطوري على الأجهزة الضعيفة
🚀 بدون تقطيع أو لاج

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📱 **المواصفات:**
📦 {data['file_size']}
📌 {version_num}
🔢 {data['version_code']}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

💯 ضمان الجودة 100%
⚡️ حملها الآن وجرب الفرق""",
        
        "vip": f"""👑 **{data['name']} {version_num} - نسخة VIP** 👑

✨ **للمتميزين فقط**
💎 أفضل إصدار على الإطلاق

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🔥 **مزايا حصرية:**
• أداء خرافي
• ثبات تام
• بدون مشاكل
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

📊 {data['file_size']} | {version_num}
✅ مجربة وآمنة 100%"""
    }
    
    app_data[user_id]['description'] = descriptions.get(desc_type, descriptions['strong'])
    app_data[user_id]['version_num'] = version_num
    
    await query.edit_message_text("✅ تم اختيار الوصف، جاري النشر...")
    await publish_app(update, context, user_id)
    return ConversationHandler.END

async def get_custom_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام وصف مخصص"""
    user_id = update.effective_user.id
    description = update.message.text
    
    if user_id not in app_data:
        await update.message.reply_text("❌ انتهت الجلسة، أرسل /start مرة أخرى")
        return ConversationHandler.END
    
    app_data[user_id]['description'] = description
    app_data[user_id]['version_num'] = get_next_version()
    
    await update.message.reply_text("✅ تم حفظ الوصف، جاري النشر...")
    await publish_app(update, context, user_id)
    return ConversationHandler.END

async def publish_app(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """نشر التطبيق في القناة"""
    data = app_data[user_id]
    version_num = data['version_num']
    app_id = f"app_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # حفظ الكود إذا وجد
    codes_data = load_codes()
    if data.get('has_code', False) and data.get('code_key'):
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
        'uploader_name': update.effective_user.mention_html(),
        'has_code': data.get('has_code', False),
        'code_key': data.get('code_key') if data.get('has_code', False) else None
    }
    save_downloads(downloads)
    
    # تحديث حالة البوت
    bot_state = load_bot_state()
    if 'apps_list' not in bot_state:
        bot_state['apps_list'] = []
    
    bot_state['apps_list'].insert(0, {  # إدراج في البداية
        'app_id': app_id,
        'name': data['name'],
        'version': version_num,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'downloads': 0
    })
    
    # الاحتفاظ بآخر 100 تطبيق فقط
    if len(bot_state['apps_list']) > 100:
        bot_state['apps_list'] = bot_state['apps_list'][:100]
    
    bot_state['last_app_id'] = app_id
    bot_state['total_apps'] = len(downloads)
    bot_state['total_downloads'] = sum(a.get('downloads', 0) for a in downloads.values())
    save_bot_state(bot_state)
    
    # تجهيز الكيبورد المتطور
    keyboard_buttons = [
        [
            InlineKeyboardButton(f"📥 تحميل", callback_data=f"download_{app_id}"),
            InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info_{app_id}")
        ]
    ]
    
    if data.get('has_code', False) and data.get('code_key'):
        keyboard_buttons[0].insert(1, InlineKeyboardButton("🔑 الكود", callback_data=f"code_{app_id}"))
    
    # إضافة أزرار إضافية
    keyboard_buttons.append([
        InlineKeyboardButton("📊 الإحصائيات", callback_data="global_stats"),
        InlineKeyboardButton("📱 القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
    ])
    
    # إرسال للقناة
    sent_message = await context.bot.send_photo(
        CHANNEL_USERNAME,
        data['photo'],
        caption=data['description'],
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
        parse_mode='Markdown'
    )
    
    # حفظ message_id للرجوع إليه
    downloads[app_id]['message_id'] = sent_message.message_id
    save_downloads(downloads)
    
    # إرسال تأكيد للمستخدم
    confirm_text = f"""✅ **تم النشر بنجاح!**

📱 **التطبيق:** {data['name']}
📌 **الإصدار:** {version_num}
📢 **القناة:** {CHANNEL_USERNAME}
🆔 **المعرف:** `{app_id}`"""

    if data.get('has_code', False) and data.get('code_key'):
        expiry_info = f"\n🔑 **الكود:** `{data['code_key']}`"
        if data.get('expiry_days'):
            expiry_info += f"\n⏳ **المدة:** {data['expiry_days']} يوم"
        else:
            expiry_info += f"\n♾️ **بدون انتهاء**"
        confirm_text += expiry_info
    
    await context.bot.send_message(
        chat_id=user_id,
        text=confirm_text,
        parse_mode='Markdown'
    )
    
    # إنشاء نسخة احتياطية كل 10 تطبيقات
    if len(downloads) % 10 == 0:
        asyncio.create_task(create_backup())
    
    del app_data[user_id]

# ==================== دوال التفاعل ====================

async def download_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر التحميل"""
    query = update.callback_query
    user_id = query.from_user.id
    user = query.from_user
    await query.answer("📦 جاري التحميل...")
    
    # تتبع المستخدم
    track_user(user_id, user.username, user.first_name)
    
    app_id = query.data.replace("download_", "")
    downloads = load_downloads()
    app = downloads.get(app_id)
    
    if not app:
        await query.edit_message_text("❌ **التطبيق غير موجود**", parse_mode='Markdown')
        return
    
    # إرسال رسالة الحالة
    status_msg = await context.bot.send_message(
        chat_id=user_id,
        text=f"📦 **جاري تجهيز {app['name']}**\n\n⏳ الرجاء الانتظار...",
        parse_mode='Markdown'
    )
    
    try:
        # التحقق من اليوزربوت
        if not await ensure_userbot():
            await status_msg.edit_text(
                "❌ **عذراً، البوت تحت الصيانة**\n\n"
                "يرجى المحاولة لاحقاً",
                parse_mode='Markdown'
            )
            return
        
        # تحميل الملف
        await status_msg.edit_text("📥 **جاري تحميل الملف...**", parse_mode='Markdown')
        file = await context.bot.get_file(app['file_id'])
        
        # إنشاء ملف مؤقت
        with tempfile.NamedTemporaryFile(delete=False, suffix='.apk') as tmp:
            path = tmp.name
        
        # تحميل الملف مع عرض التقدم
        success = await download_with_progress(user_id, file, path, status_msg)
        if not success:
            if os.path.exists(path):
                os.remove(path)
            return
        
        # إرسال الملف
        await status_msg.edit_text("📤 **جاري الإرسال...**", parse_mode='Markdown')
        
        caption = f"""✅ **{app['name']} {app['version']}**

📥 تم التحميل بنجاح
⚡️ استمتع بالتجربة
        
📊 **{app['file_size']}** | الإصدار: **{app['version_code']}**"""
        
        await user_client.send_file(
            user_id, 
            path, 
            caption=caption, 
            parse_mode='Markdown',
            attributes=[DocumentAttributes(filename=app['file_name'])]
        )
        
        # تنظيف
        os.remove(path)
        
        # تحديث العداد
        new_count = increment_download_count(app_id)
        increment_user_downloads(user_id)
        
        # تحديث الزر في القناة
        try:
            keyboard_buttons = [
                [
                    InlineKeyboardButton(f"📥 تحميل ({new_count})", callback_data=f"download_{app_id}"),
                    InlineKeyboardButton("ℹ️ معلومات", callback_data=f"info_{app_id}")
                ]
            ]
            if app.get('has_code', False) and app.get('code_key'):
                keyboard_buttons[0].insert(1, InlineKeyboardButton("🔑 الكود", callback_data=f"code_{app_id}"))
            
            keyboard_buttons.append([
                InlineKeyboardButton("📊 الإحصائيات", callback_data="global_stats"),
                InlineKeyboardButton("📱 القناة", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
            ])
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard_buttons))
        except Exception as e:
            logger.error(f"⚠️ خطأ في تحديث الزر: {e}")
        
        await status_msg.edit_text(
            f"✅ **تم الإرسال بنجاح!**\n\n"
            f"📱 {app['name']}\n"
            f"📥 عدد التحميلات: {new_count}",
            parse_mode='Markdown'
        )
        
    except errors.FloodWaitError as e:
        wait_time = e.seconds
        await status_msg.edit_text(
            f"⚠️ **تقييد من تليجرام**\n\n"
            f"الرجاء الانتظار {wait_time // 60} دقيقة",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ خطأ في التحميل: {e}")
        await status_msg.edit_text(
            f"❌ **حدث خطأ**\n\n"
            f"`{str(e)[:100]}`",
            parse_mode='Markdown'
        )
        
        if 'path' in locals() and os.path.exists(path):
            os.remove(path)

async def code_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر الكود"""
    query = update.callback_query
    user_id = query.from_user.id
    user = query.from_user
    await query.answer("🔑 جاري تجهيز الكود...")
    
    # تتبع المستخدم
    track_user(user_id, user.username, user.first_name)
    increment_user_codes(user_id)
    
    app_id = query.data.replace("code_", "")
    downloads = load_downloads()
    app = downloads.get(app_id)
    
    if not app or not app.get('code_key'):
        await query.edit_message_text("❌ **الكود غير موجود**", parse_mode='Markdown')
        return
    
    # التحقق من الصلاحية
    codes_data = load_codes()
    expiry_date = codes_data.get('expiry_dates', {}).get(app['version'])
    
    if expiry_date and not check_code_expiry(expiry_date):
        await query.edit_message_text(
            f"❌ **الكود منتهي الصلاحية**\n\n"
            f"📅 تاريخ الانتهاء: {expiry_date}",
            parse_mode='Markdown'
        )
        return
    
    # إنشاء رسالة الكود بتصميم جذاب
    code_message = f"""🔑 **كود {app['version']}**

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
`{app['code_key']}`
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

📱 **التطبيق:** {app['name']}
📊 **الحالة:** {get_code_status(expiry_date)}

💡 **انسخ الكود واستخدمه**"""
    
    # إرسال الكود في الخاص
    await context.bot.send_message(
        chat_id=user_id,
        text=code_message,
        parse_mode='Markdown'
    )
    
    await query.edit_message_text("✅ **تم إرسال الكود إلى الخاص**", parse_mode='Markdown')

async def info_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات التطبيق"""
    query = update.callback_query
    await query.answer()
    
    app_id = query.data.replace("info_", "")
    downloads = load_downloads()
    app = downloads.get(app_id)
    
    if not app:
        await query.edit_message_text("❌ **التطبيق غير موجود**", parse_mode='Markdown')
        return
    
    code_info = ""
    if app.get('has_code', False) and app.get('code_key'):
        codes_data = load_codes()
        expiry_date = codes_data.get('expiry_dates', {}).get(app['version'])
        code_info = f"\n🔑 **الكود:** متوفر\n📊 **حالة الكود:** {get_code_status(expiry_date)}"
    
    info_text = f"""ℹ️ **معلومات التطبيق**

📱 **الاسم:** {app['name']}
📌 **الإصدار:** {app['version']}
🔢 **كود الإصدار:** {app['version_code']}
📦 **الحجم:** {app['file_size']}
📅 **تاريخ الرفع:** {app['date']}
⏰ **الوقت:** {app.get('time', '00:00')}
📥 **مرات التحميل:** {app.get('downloads', 0)}
👤 **رافع التطبيق:** {app.get('uploader_name', 'غير معروف')}
{code_info}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
✅ **تطبيق آمن ومجرب 100%**"""
    
    keyboard_buttons = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"back_{app_id}")]]
    
    await query.edit_message_caption(
        caption=info_text,
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
        parse_mode='Markdown'
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
            reply_markup=InlineKeyboardMarkup(keyboard_buttons),
            parse_mode='Markdown'
        )

async def global_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإحصائيات العامة"""
    query = update.callback_query
    await query.answer()
    
    downloads = load_downloads()
    users = load_users()
    codes_data = load_codes()
    stats = load_stats()
    bot_state = load_bot_state()
    
    total_apps = len(downloads)
    total_downloads = sum(a.get('downloads', 0) for a in downloads.values())
    total_users = users.get('total_users', 0)
    total_codes = len(codes_data.get('codes', {}))
    
    # حساب الكودات النشطة
    active_codes = 0
    for version, expiry in codes_data.get('expiry_dates', {}).items():
        if check_code_expiry(expiry):
            active_codes += 1
    
    # حساب وقت التشغيل
    start_time = datetime.fromisoformat(bot_state.get('start_time', datetime.now().isoformat()))
    uptime = datetime.now() - start_time
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    # أشهر 5 تطبيقات
    popular = ""
    top_apps = stats.get('popular_apps', [])[:5]
    for i, app in enumerate(top_apps, 1):
        popular += f"{i}. **{app['name']}** - {app['downloads']} 📥\n"
    
    stats_text = f"""📊 **إحصائيات البوت العامة**

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📱 **التطبيقات:** {total_apps}
👥 **المستخدمين:** {total_users}
📥 **إجمالي التحميلات:** {total_downloads}
🔑 **الكودات:** {total_codes} (نشط: {active_codes})
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📅 **اليوم:** {stats.get('last_24h', 0)} تحميل
⏰ **وقت التشغيل:** {days} يوم {hours} ساعة
💾 **آخر نسخة:** {bot_state.get('last_backup', 'لا يوجد')[:10] if bot_state.get('last_backup') else 'لا يوجد'}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🏆 **الأكثر تحميلاً:**
{popular if popular else 'لا توجد بيانات'}"""
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
    
    if query.message.photo:
        await query.edit_message_caption(
            caption=stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            text=stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    
    # إرسال رسالة البداية
    user = query.from_user
    await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية"""
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    await update.message.reply_text("❌ **تم الإلغاء**", parse_mode='Markdown')
    return ConversationHandler.END

# ==================== أوامر المشرف ====================

async def admin_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار حالة البوت"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ **هذا الأمر للمشرف فقط**", parse_mode='Markdown')
        return
    
    status_msg = await update.message.reply_text("🔍 **جاري الفحص...**", parse_mode='Markdown')
    
    try:
        # فحص اليوزربوت
        userbot_ok = await ensure_userbot() if user_client else False
        
        # فحص الملفات
        files_status = []
        for file in [DOWNLOADS_FILE, VERSION_COUNTER_FILE, BOT_STATE_FILE, CODES_FILE, USERS_FILE, STATS_FILE]:
            if os.path.exists(file):
                size = os.path.getsize(file)
                files_status.append(f"✅ {file} ({get_file_size(size)})")
            else:
                files_status.append(f"❌ {file} (غير موجود)")
        
        # إحصائيات سريعة
        downloads = load_downloads()
        users = load_users()
        codes = load_codes()
        
        status_text = f"""📊 **حالة البوت**

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🤖 **البوت:** ✅ يعمل
👤 **اليوزربوت:** {'✅ يعمل' if userbot_ok else '❌ لا يعمل'}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📁 **الملفات:**
{chr(10).join(files_status[:5])}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📊 **إحصائيات:**
• التطبيقات: {len(downloads)}
• المستخدمين: {users.get('total_users', 0)}
• الكودات: {len(codes.get('codes', {}))}"""
        
        await status_msg.edit_text(status_text, parse_mode='Markdown')
        
    except Exception as e:
        await status_msg.edit_text(f"❌ **خطأ:** {str(e)}", parse_mode='Markdown')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات متقدمة للمشرف"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    downloads = load_downloads()
    users = load_users()
    codes_data = load_codes()
    stats = load_stats()
    bot_state = load_bot_state()
    
    total_apps = len(downloads)
    total_downloads = sum(a.get('downloads', 0) for a in downloads.values())
    total_users = users.get('total_users', 0)
    total_codes = len(codes_data.get('codes', {}))
    
    # تفاصيل الكودات
    active_codes = 0
    expired_codes = 0
    for version, expiry in codes_data.get('expiry_dates', {}).items():
        if check_code_expiry(expiry):
            active_codes += 1
        else:
            expired_codes += 1
    
    # تفاصيل المستخدمين
    active_today = 0
    today = datetime.now().strftime('%Y-%m-%d')
    for uid, uinfo in users.get('users', {}).items():
        if uinfo.get('last_seen', '').startswith(today):
            active_today += 1
    
    # آخر 10 تطبيقات
    recent_apps = ""
    for app in bot_state.get('apps_list', [])[:10]:
        recent_apps += f"• {app['name']} - {app['version']} ({app['downloads']} 📥)\n"
    
    stats_text = f"""📊 **إحصائيات المشرف**

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📱 **التطبيقات:** {total_apps}
📥 **إجمالي التحميلات:** {total_downloads}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
👥 **المستخدمين:**
• الإجمالي: {total_users}
• نشط اليوم: {active_today}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
🔑 **الكودات:**
• الإجمالي: {total_codes}
• نشط: {active_codes}
• منتهي: {expired_codes}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📅 **آخر التطبيقات:**
{recent_apps if recent_apps else 'لا توجد'}"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def admin_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنشاء نسخة احتياطية يدوياً"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    status_msg = await update.message.reply_text("📦 **جاري إنشاء نسخة احتياطية...**", parse_mode='Markdown')
    
    if await create_backup():
        await status_msg.edit_text("✅ **تم إنشاء النسخة الاحتياطية بنجاح**", parse_mode='Markdown')
    else:
        await status_msg.edit_text("❌ **فشل إنشاء النسخة الاحتياطية**", parse_mode='Markdown')

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة التطبيقات"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    bot_state = load_bot_state()
    apps_list = bot_state.get('apps_list', [])
    
    if not apps_list:
        await update.message.reply_text("📭 **لا توجد تطبيقات بعد**", parse_mode='Markdown')
        return
    
    text = "📱 **قائمة التطبيقات:**\n\n"
    for i, app in enumerate(apps_list[:20], 1):
        text += f"{i}. **{app['name']}** - {app['version']}\n   📥 {app.get('downloads', 0)} | {app['date']}\n"
    
    if len(apps_list) > 20:
        text += f"\n... و {len(apps_list) - 20} تطبيق آخر"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة لجميع المستخدمين"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ **استخدام:** /broadcast <الرسالة>",
            parse_mode='Markdown'
        )
        return
    
    message = ' '.join(context.args)
    users = load_users()
    
    status_msg = await update.message.reply_text(
        f"📤 **جاري الإرسال لـ {len(users.get('users', {}))} مستخدم...**",
        parse_mode='Markdown'
    )
    
    sent = 0
    failed = 0
    
    for uid in users.get('users', {}):
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"📢 **رسالة من الإدارة**\n\n{message}",
                parse_mode='Markdown'
            )
            sent += 1
            await asyncio.sleep(0.05)  # تجنب الحظر
        except Exception as e:
            failed += 1
            logger.error(f"فشل إرسال لـ {uid}: {e}")
    
    await status_msg.edit_text(
        f"✅ **تم الإرسال**\n\n"
        f"📨 نجح: {sent}\n"
        f"❌ فشل: {failed}",
        parse_mode='Markdown'
    )

# ==================== معالجة رسائل المجموعة ====================

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة طلبات الكود في المجموعة"""
    message = update.message
    if not message.text or not message.chat:
        return
    
    # التحقق من المجموعة
    if message.chat.username and message.chat.username.lower() == 'gsn_mod_developer':
        text = message.text.strip()
        text_lower = text.lower()
        
        # البحث عن الكود
        codes_data = load_codes()
        
        for version, code_info in codes_data.get('codes', {}).items():
            version_lower = version.lower()
            
            # أنماط الطلب المختلفة
            patterns = [
                version_lower,
                f"كود {version_lower}",
                f"key {version_lower}",
                f"{version_lower} كود",
                f"الكود {version_lower}",
                version_lower.replace('v', 'كود ')
            ]
            
            if any(pattern in text_lower for pattern in patterns):
                expiry_date = codes_data.get('expiry_dates', {}).get(version)
                
                if check_code_expiry(expiry_date):
                    response = f"""🔑 **كود {version}**

`{code_info['key']}`

📱 **التطبيق:** {code_info['app_name']}
📊 **الحالة:** {get_code_status(expiry_date)}"""
                else:
                    response = f"""❌ **كود {version} منتهي الصلاحية**

📅 تاريخ الانتهاء: {expiry_date}"""
                
                await message.reply_text(response, parse_mode='Markdown')
                
                # تتبع المستخدم
                if message.from_user:
                    track_user(
                        message.from_user.id,
                        message.from_user.username,
                        message.from_user.first_name
                    )
                return

# ==================== تشغيل البوت ====================

async def run_bot():
    """تشغيل البوت"""
    logger.info("🚀 جاري تشغيل البوت المتطور...")
    
    # تحميل الحالة
    bot_state = load_bot_state()
    logger.info(f"📊 الحالة السابقة: {bot_state.get('total_apps', 0)} تطبيق")
    
    # تشغيل اليوزربوت
    userbot_success = await init_userbot()
    if userbot_success:
        logger.info("✅ اليوزربوت يعمل بنجاح")
    else:
        logger.error("❌ فشل تشغيل اليوزربوت - بعض الميزات قد لا تعمل")
    
    # إنشاء التطبيق
    app = Application.builder().token(BOT_TOKEN).build()
    
    # معالج رسائل المجموعة
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message), group=1)
    
    # محادثة رفع التطبيقات
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            FILE: [MessageHandler(filters.Document.ALL, get_file)],
            VERSION_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_version_code)],
            CODE_KEY: [
                CallbackQueryHandler(code_decision, pattern="^code_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_code_key)
            ],
            CODE_EXPIRY: [CallbackQueryHandler(get_expiry, pattern="^expiry_")],
            DESCRIPTION: [
                CallbackQueryHandler(description_callback, pattern="^desc_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_custom_description)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # إضافة المعالجات
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(download_button, pattern="^download_"))
    app.add_handler(CallbackQueryHandler(code_button, pattern="^code_"))
    app.add_handler(CallbackQueryHandler(info_button, pattern="^info_"))
    app.add_handler(CallbackQueryHandler(back_button, pattern="^back_"))
    app.add_handler(CallbackQueryHandler(global_stats, pattern="^global_stats$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(continue_anyway, pattern="^continue_anyway$"))
    
    # أوامر المشرف
    app.add_handler(CommandHandler('test', admin_test))
    app.add_handler(CommandHandler('stats', admin_stats))
    app.add_handler(CommandHandler('backup', admin_backup))
    app.add_handler(CommandHandler('list', admin_list))
    app.add_handler(CommandHandler('broadcast', admin_broadcast))
    
    logger.info("✅ البوت جاهز للعمل!")
    
    # تشغيل البوت
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        # إنشاء نسخة احتياطية كل ساعة
        while True:
            await asyncio.sleep(3600)  # كل ساعة
            if user_client and user_client.is_connected():
                asyncio.create_task(create_backup())
                
    except KeyboardInterrupt:
        logger.info("🛑 جاري إيقاف البوت...")
        await create_backup()  # نسخة احتياطية قبل الإيقاف
        save_bot_state(load_bot_state())
        await app.stop()
        if user_client:
            await user_client.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("👋 تم إيقاف البوت")
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {e}")
        # محاولة إنشاء نسخة احتياطية حتى في حالة الخطأ
        try:
            asyncio.run(create_backup())
        except:
            pass
