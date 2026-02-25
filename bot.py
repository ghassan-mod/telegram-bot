import os
import asyncio
import json
import tempfile
import random
from datetime import datetime, timedelta
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import logging

# إعدادات التسجيل
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# متغيرات البيئة
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PHONE_NUMBER = os.environ.get('PHONE_NUMBER')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME')
SESSION_STRING = os.environ.get('SESSION_STRING', '')

if not CHANNEL_USERNAME.startswith('@'):
    CHANNEL_USERNAME = '@' + CHANNEL_USERNAME

# إعدادات البوت
NAME, PHOTO, FILE, VERSION_CODE, DESCRIPTION, CODE_KEY, CODE_EXPIRY = range(7)
app_data = {}
DOWNLOADS_FILE = "downloads_counter.json"
VERSION_COUNTER_FILE = "version_counter.json"
BOT_STATE_FILE = "bot_state.json"
CODES_FILE = "codes_database.json"  # ملف خاص بالكودات

# التأكد من وجود مجلد temp
temp_dir = tempfile.gettempdir()
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# دوال المساعدة للحفظ والتحميل
def load_json_file(filename, default=None):
    if default is None:
        default = {} if 'counter' not in filename else 0
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في تحميل {filename}: {e}")
    return default

def save_json_file(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ {filename}: {e}")

def load_downloads():
    return load_json_file(DOWNLOADS_FILE, {})

def save_downloads(downloads):
    save_json_file(DOWNLOADS_FILE, downloads)

def load_version_counter():
    data = load_json_file(VERSION_COUNTER_FILE, {'last_version': 0})
    return data.get('last_version', 0)

def save_version_counter(version):
    save_json_file(VERSION_COUNTER_FILE, {'last_version': version})

def load_bot_state():
    return load_json_file(BOT_STATE_FILE, {'last_app_id': None, 'total_apps': 0, 'apps_list': []})

def save_bot_state(state):
    save_json_file(BOT_STATE_FILE, state)

def load_codes():
    """تحميل قاعدة بيانات الكودات"""
    return load_json_file(CODES_FILE, {'codes': {}, 'expiry_dates': {}})

def save_codes(codes_data):
    """حفظ قاعدة بيانات الكودات"""
    save_json_file(CODES_FILE, codes_data)

def get_next_version():
    current = load_version_counter()
    next_version = current + 1
    save_version_counter(next_version)
    return f"V{next_version}"

def get_file_size(size):
    if size < 1024 * 1024:
        return f"{size/1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size/(1024*1024):.1f} MB"
    else:
        return f"{size/(1024*1024*1024):.1f} GB"

def increment_download_count(app_id):
    downloads = load_downloads()
    if app_id in downloads:
        downloads[app_id]['downloads'] += 1
        save_downloads(downloads)
        return downloads[app_id]['downloads']
    return 0

def generate_code_key(version, app_name):
    """توليد كود عشوائي"""
    import random
    import string
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    return f"KEY-{code}"

def check_code_expiry(expiry_date):
    """التحقق من صلاحية الكود"""
    if not expiry_date:
        return True  # بدون تاريخ انتهاء -> دائمًا صالح
    expiry = datetime.fromisoformat(expiry_date)
    return datetime.now() < expiry

def get_code_status(expiry_date):
    """الحصول على حالة الكود"""
    if not expiry_date:
        return "✅ دائم (بدون انتهاء)"
    expiry = datetime.fromisoformat(expiry_date)
    remaining = expiry - datetime.now()
    if remaining.days < 0:
        return "❌ منتهي الصلاحية"
    elif remaining.days == 0:
        hours = remaining.seconds // 3600
        return f"⚠️ ينتهي اليوم (بعد {hours} ساعة)"
    else:
        return f"⏳ متبقي {remaining.days} يوم"

# دوال التعامل مع الكودات
async def handle_code_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة طلب الكود في المجموعة"""
    message = update.message
    if not message.text or not message.chat.username == 'GSN_MOD_Developer':
        return
    
    text = message.text.strip().lower()
    codes_data = load_codes()
    
    # البحث عن الكود المطلوب
    for version, code_info in codes_data['codes'].items():
        if text in [version.lower(), f"كود {version.lower()}", f"key {version.lower()}", f"{version.lower()} كود"]:
            # التحقق من الصلاحية
            expiry_date = codes_data['expiry_dates'].get(version)
            if check_code_expiry(expiry_date):
                await message.reply_text(
                    f"🔑 **كود {version}**\n\n"
                    f"`{code_info['key']}`\n\n"
                    f"📱 **التطبيق:** {code_info['app_name']}\n"
                    f"📊 **الحالة:** {get_code_status(expiry_date)}",
                    parse_mode='Markdown'
                )
            else:
                await message.reply_text(
                    f"❌ **كود {version} منتهي الصلاحية**\n\n"
                    f"تاريخ الانتهاء: {expiry_date}",
                    parse_mode='Markdown'
                )
            return

# تشغيل اليوزربوت
user_client = None

async def validate_userbot_session():
    global user_client
    try:
        if user_client and user_client.is_connected():
            await user_client.get_me()
            return True
    except Exception as e:
        logger.error(f"خطأ في التحقق من جلسة اليوزربوت: {e}")
    return False

async def init_userbot():
    global user_client
    try:
        logger.info("🔄 جاري تشغيل اليوزربوت...")
        
        if SESSION_STRING:
            user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
            await user_client.connect()
        else:
            user_client = TelegramClient('user_session', API_ID, API_HASH)
            await user_client.start(phone=PHONE_NUMBER)
            session_str = user_client.session.save()
            logger.info(f"🔑 SESSION_STRING={session_str}")
        
        me = await user_client.get_me()
        logger.info(f"✅ اليوزربوت شغال كـ: {me.first_name}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تشغيل اليوزربوت: {e}")
        return False

async def ensure_userbot():
    global user_client
    try:
        if user_client is None:
            success = await init_userbot()
            if not success:
                return False
        if not user_client.is_connected():
            await user_client.connect()
        
        if not await validate_userbot_session():
            logger.warning("جلسة اليوزربوت غير صالحة، جاري إعادة الاتصال...")
            await user_client.disconnect()
            await user_client.connect()
        
        return True
    except Exception as e:
        logger.error(f"خطأ في ensure_userbot: {e}")
        return False

async def download_with_timeout(coroutine, timeout=60):
    try:
        return await asyncio.wait_for(coroutine, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("انتهت مهلة التحميل")
        return None
    except Exception as e:
        logger.error(f"خطأ في التحميل: {e}")
        return None

# دوال البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"✨ مرحباً {user.first_name}!\n\n"
        "📱 أرسل **اسم التطبيق** للبدء"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    app_data[user_id] = {'name': update.message.text}
    await update.message.reply_text("✅ تم، أرسل **صورة التطبيق**")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = await update.message.photo[-1].get_file()
    app_data[user_id]['photo'] = photo.file_id
    await update.message.reply_text("✅ تم، أرسل **ملف التطبيق**")
    return FILE

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ أرسل ملف صالح")
        return FILE
    
    app_data[user_id]['file_id'] = doc.file_id
    app_data[user_id]['file_name'] = doc.file_name
    app_data[user_id]['file_size'] = get_file_size(doc.file_size)
    app_data[user_id]['raw_size'] = doc.file_size
    
    await update.message.reply_text("🔢 أرسل **كود النسخة** (مثال: 1.0.0)")
    return VERSION_CODE

async def get_version_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    version = update.message.text
    if version.lower() in ['بدون', 'لا', 'none']:
        version = "1.0.0"
    
    app_data[user_id]['version_code'] = version
    
    # سؤال عن إضافة كود خاص
    keyboard = [
        [InlineKeyboardButton("✅ نعم، أضف كود", callback_data="code_yes")],
        [InlineKeyboardButton("❌ لا، بدون كود", callback_data="code_no")]
    ]
    
    await update.message.reply_text(
        "🔑 **هل تريد إضافة كود خاص للتطبيق؟**\n\n"
        "عند إضافة كود، المستخدمين يقدرون يطلبونه في المجموعة",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CODE_KEY

async def code_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id not in app_data:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل /start مرة أخرى")
        return ConversationHandler.END
    
    if query.data == "code_yes":
        app_data[user_id]['has_code'] = True
        await query.edit_message_text(
            "🔑 **أرسل الكود الخاص بالتطبيق**\n\n"
            "مثال: GSN-PRO-2024\n\n"
            "⚠️ الكود سيتم حفظه في قاعدة البيانات"
        )
        return CODE_KEY
    else:
        app_data[user_id]['has_code'] = False
        app_data[user_id]['code_key'] = None
        app_data[user_id]['expiry_days'] = None
        # الانتقال لاختيار الوصف
        await show_description_options(update, context, user_id)
        return DESCRIPTION

async def get_code_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text
    
    app_data[user_id]['code_key'] = code
    
    # سؤال عن مدة الصلاحية
    keyboard = [
        [InlineKeyboardButton("📅 30 يوم", callback_data="expiry_30")],
        [InlineKeyboardButton("📅 60 يوم", callback_data="expiry_60")],
        [InlineKeyboardButton("📅 90 يوم", callback_data="expiry_90")],
        [InlineKeyboardButton("♾️ بدون انتهاء", callback_data="expiry_forever")]
    ]
    
    await update.message.reply_text(
        "⏳ **كم مدة صلاحية الكود؟**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CODE_EXPIRY

async def get_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    await query.edit_message_text("✅ تم تحديد المدة، جاري اختيار الوصف...")
    
    # الانتقال لاختيار الوصف
    await show_description_options(update, context, user_id)
    return DESCRIPTION

async def show_description_options(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """عرض خيارات الوصف"""
    keyboard = [
        [InlineKeyboardButton("🔥 وصف قوي", callback_data="desc_strong")],
        [InlineKeyboardButton("✨ وصف احترافي", callback_data="desc_professional")],
        [InlineKeyboardButton("⚡️ وصف خرافي", callback_data="desc_amazing")],
        [InlineKeyboardButton("🎯 وصف للمحترفين", callback_data="desc_pro")],
        [InlineKeyboardButton("📝 كتابة وصف مخصص", callback_data="desc_custom")]
    ]
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(
            "📝 **اختر نوع الوصف للتطبيق:**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text="📝 **اختر نوع الوصف للتطبيق:**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def description_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id not in app_data:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل /start مرة أخرى")
        return ConversationHandler.END
    
    desc_type = query.data.replace("desc_", "")
    
    if desc_type == "custom":
        await query.edit_message_text("📝 أرسل الوصف الذي تريده:")
        return DESCRIPTION
    
    # توليد وصف تلقائي
    data = app_data[user_id]
    version_num = get_next_version()
    
    descriptions = {
        "strong": f"""🔥 **{data['name']} {version_num} - مخصوص للأجهزة الضعيفة!** 🔥

⚡️ لو جهازك ضعيف... ولا يهمك!
النسخة دي معمولة عشان تطيرك في اللعبة بدون لاج ولا تهنيج! 🚀

🎮 **ثبات أكثر - لاج أقل - أداء خرافي للأجهزة الضعيفة**
سيطر على اللعبة يا زعيم 💥😈

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📦 **معلومات التطبيق:**
• الحجم: {data['file_size']}
• الإصدار: {version_num}
• الكود: {data['version_code']}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

✅ **مضمونة 100%** - مجربة وشغالة بدون مشاكل
⚡️ **تحديث مستمر** - أحدث إصدار مع كل التحديثات""",
        
        "professional": f"""✨ **{data['name']} {version_num} - النسخة الذهبية!** ✨

🚀 **أسرع نسخة على الإطلاق** - مصممة خصيصاً للأداء العالي
🎯 **بدون أي تهنيج** - حتى على أضعف الأجهزة

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
💪 **مميزات حصرية:**
✓ ثبات في الإطارات FPS
✓ استهلاك أقل للرام
✓ بطارية تدوم أطول
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

📊 **التفاصيل:**
📦 الحجم: {data['file_size']}
📌 الإصدار: {version_num}
🔢 الكود: {data['version_code']}

🔥 **نضمنلك تجربة أسطورية** - حملها وجرب الفرق بنفسك!""",
        
        "amazing": f"""⚡️ **{data['name']} {version_num} - النسخة الخرافية** ⚡️

🎯 **صممت خصيصاً للمحترفين**
🏆 **أفضل أداء - أقل لاج - أسرع استجابة**

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
💎 **ليه تختار النسخة دي؟**
✅ تشتغل على كل الأجهزة
✅ تحديثات مستمرة
✅ دعم فني 24/7
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

📥 **التحميل مباشر وآمن**
📊 {data['file_size']} | {version_num} | {data['version_code']}

✅ **مجربة وآمنة 100%** 
🌟 ثقة الآلاف من المستخدمين""",
        
        "pro": f"""🎯 **{data['name']} {version_num} - للمحترفين فقط** 🎯

🔥 **الأداء الأسطوري** على الأجهزة الضعيفة!
🚀 تطير في اللعبة بدون أي تقطيع

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
📱 **مواصفات النسخة:**
📦 الحجم: {data['file_size']}
📌 الإصدار: {version_num}
🔢 الكود: {data['version_code']}
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

💯 **ضمان الجودة:**
✓ مجربة على جميع الأجهزة
✓ بدون إعلانات مزعجة
✓ تحديثات أسبوعية

⚡️ **حملها الآن وجرب الفرق!**"""
    }
    
    app_data[user_id]['description'] = descriptions.get(desc_type, descriptions['strong'])
    app_data[user_id]['version_num'] = version_num
    
    await query.edit_message_text("✅ تم اختيار الوصف، جاري النشر...")
    
    # متابعة النشر
    await publish_app(update, context, user_id)
    return ConversationHandler.END

async def get_custom_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    """نشر التطبيق في القناة وحفظ البيانات"""
    data = app_data[user_id]
    version_num = data['version_num']
    app_id = f"app_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # حفظ الكود إذا وجد
    codes_data = load_codes()
    if data.get('has_code', False) and data.get('code_key'):
        codes_data['codes'][version_num] = {
            'key': data['code_key'],
            'app_name': data['name'],
            'version': version_num
        }
        
        # حساب تاريخ الانتهاء
        if data.get('expiry_days'):
            expiry_date = (datetime.now() + timedelta(days=data['expiry_days'])).isoformat()
            codes_data['expiry_dates'][version_num] = expiry_date
        
        save_codes(codes_data)
    
    # حفظ التطبيق في قاعدة البيانات
    downloads = load_downloads()
    downloads[app_id] = {
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
        'uploader_id': user_id,
        'uploader_name': update.effective_user.mention_html(),
        'has_code': data.get('has_code', False),
        'code_key': data.get('code_key') if data.get('has_code', False) else None
    }
    save_downloads(downloads)
    
    # تحديث حالة البوت (حفظ جميع التطبيقات)
    bot_state = load_bot_state()
    if 'apps_list' not in bot_state:
        bot_state['apps_list'] = []
    
    bot_state['apps_list'].append({
        'app_id': app_id,
        'name': data['name'],
        'version': version_num,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    bot_state['last_app_id'] = app_id
    bot_state['total_apps'] = len(downloads)
    save_bot_state(bot_state)
    
    # تجهيز الكيبورد
    keyboard_buttons = [
        [InlineKeyboardButton(f"📥 تحميل ({version_num})", callback_data=f"download_{app_id}")],
        [InlineKeyboardButton("ℹ️ معلومات التطبيق", callback_data=f"info_{app_id}")]
    ]
    
    # إضافة زر الكود إذا وجد
    if data.get('has_code', False) and data.get('code_key'):
        keyboard_buttons.insert(1, [InlineKeyboardButton("🔑 طلب الكود", callback_data=f"code_{app_id}")])
    
    # إرسال للقناة
    await context.bot.send_photo(
        CHANNEL_USERNAME,
        data['photo'],
        caption=data['description'],
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
        parse_mode='Markdown'
    )
    
    # إرسال تأكيد للمستخدم
    confirmation = f"""✅ **تم النشر بنجاح!**

📱 **التطبيق:** {data['name']}
📌 **الإصدار:** {version_num}
📢 **القناة:** {CHANNEL_USERNAME}"""

    if data.get('has_code', False) and data.get('code_key'):
        expiry_info = f"\n🔑 **الكود:** `{data['code_key']}`"
        if data.get('expiry_days'):
            expiry_info += f"\n⏳ **مدة الصلاحية:** {data['expiry_days']} يوم"
        else:
            expiry_info += f"\n♾️ **بدون انتهاء**"
        confirmation += expiry_info
    
    await context.bot.send_message(
        chat_id=user_id,
        text=confirmation,
        parse_mode='Markdown'
    )
    
    del app_data[user_id]

# دالة التحميل
async def download_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("📦 جاري التحميل...")
    
    app_id = query.data.replace("download_", "")
    downloads = load_downloads()
    app = downloads.get(app_id)
    
    if not app:
        await query.edit_message_text("❌ التطبيق غير موجود")
        return
    
    status_msg = await context.bot.send_message(
        chat_id=user_id,
        text=f"📦 جاري تجهيز {app['name']} للتحميل..."
    )
    
    try:
        if not await ensure_userbot():
            await status_msg.edit_text("❌ مشكلة في الاتصال بالخادم، حاول مرة أخرى")
            return
        
        await status_msg.edit_text("📥 جاري تحميل الملف من الخادم...")
        file = await context.bot.get_file(app['file_id'])
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.apk') as tmp:
            path = tmp.name
        
        await status_msg.edit_text("📦 جاري تجهيز الملف للإرسال...")
        download_coro = file.download_to_drive(path)
        result = await download_with_timeout(download_coro, timeout=120)
        
        if result is None:
            await status_msg.edit_text("❌ فشل تحميل الملف (انتهت المهلة)")
            if os.path.exists(path):
                os.remove(path)
            return
        
        await status_msg.edit_text("📤 جاري إرسال الملف إلى الخاص...")
        
        caption = f"""✅ **{app['name']} {app['version']}**

📥 تم التحميل بنجاح
⚡️ استمتع بالتجربة
        
📊 {app['file_size']} | الإصدار: {app['version_code']}"""
        
        await user_client.send_file(user_id, path, caption=caption, parse_mode='Markdown')
        os.remove(path)
        
        # تحديث العداد
        new_count = increment_download_count(app_id)
        
        # تحديث الزر
        try:
            keyboard_buttons = [
                [InlineKeyboardButton(f"📥 تحميل ({new_count})", callback_data=f"download_{app_id}")],
                [InlineKeyboardButton("ℹ️ معلومات التطبيق", callback_data=f"info_{app_id}")]
            ]
            if app.get('has_code', False) and app.get('code_key'):
                keyboard_buttons.insert(1, [InlineKeyboardButton("🔑 طلب الكود", callback_data=f"code_{app_id}")])
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard_buttons))
        except Exception as e:
            logger.error(f"خطأ في تحديث الزر: {e}")
        
        await status_msg.edit_text(f"✅ تم إرسال {app['name']} إلى الخاص بنجاح!")
        
    except Exception as e:
        logger.error(f"خطأ في التحميل: {e}")
        try:
            await status_msg.edit_text("❌ حدث خطأ أثناء التحميل، حاول مرة أخرى")
        except:
            pass
        
        if 'path' in locals() and os.path.exists(path):
            os.remove(path)

async def code_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الكود الخاص بالتطبيق"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("🔑 جاري تجهيز الكود...")
    
    app_id = query.data.replace("code_", "")
    downloads = load_downloads()
    app = downloads.get(app_id)
    
    if not app or not app.get('code_key'):
        await query.edit_message_text("❌ الكود غير موجود")
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
    
    code_message = f"""🔑 **كود {app['version']}**

`{app['code_key']}`

📱 **التطبيق:** {app['name']}
📊 **الحالة:** {get_code_status(expiry_date)}"""
    
    # إرسال الكود في الخاص
    await context.bot.send_message(
        chat_id=user_id,
        text=code_message,
        parse_mode='Markdown'
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
            [InlineKeyboardButton(f"📥 تحميل ({app.get('downloads', 0)})", callback_data=f"download_{app_id}")],
            [InlineKeyboardButton("ℹ️ معلومات التطبيق", callback_data=f"info_{app_id}")]
        ]
        if app.get('has_code', False) and app.get('code_key'):
            keyboard_buttons.insert(1, [InlineKeyboardButton("🔑 طلب الكود", callback_data=f"code_{app_id}")])
        
        await query.edit_message_caption(
            caption=app['description'],
            reply_markup=InlineKeyboardMarkup(keyboard_buttons),
            parse_mode='Markdown'
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ هذا الأمر للمشرف فقط")
        return
    
    status_msg = await update.message.reply_text("🔍 جاري فحص الاتصال...")
    
    try:
        if await ensure_userbot():
            me = await user_client.get_me()
            bot_state = load_bot_state()
            codes_data = load_codes()
            
            await status_msg.edit_text(
                f"✅ **البوت يعمل بكفاءة!**\n\n"
                f"👤 **اليوزربوت:** {me.first_name}\n"
                f"📱 **إجمالي التطبيقات:** {bot_state.get('total_apps', 0)}\n"
                f"🔑 **عدد الكودات:** {len(codes_data.get('codes', {}))}\n"
                f"🔄 **آخر إصدار:** {load_version_counter()}",
                parse_mode='Markdown'
            )
        else:
            await status_msg.edit_text("❌ اليوزربوت لا يعمل")
    except Exception as e:
        await status_msg.edit_text(f"❌ خطأ: {str(e)}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    downloads = load_downloads()
    total_apps = len(downloads)
    total_downloads = sum(app.get('downloads', 0) for app in downloads.values())
    bot_state = load_bot_state()
    codes_data = load_codes()
    
    # حساب الكودات النشطة
    active_codes = 0
    for version, expiry in codes_data.get('expiry_dates', {}).items():
        if check_code_expiry(expiry):
            active_codes += 1
    
    stats_text = (
        f"📊 **إحصائيات البوت**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📱 **عدد التطبيقات:** {total_apps}\n"
        f"📥 **إجمالي التحميلات:** {total_downloads}\n"
        f"🔑 **إجمالي الكودات:** {len(codes_data.get('codes', {}))}\n"
        f"✅ **كودات نشطة:** {active_codes}\n"
        f"🔄 **آخر إصدار:** {load_version_counter()}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def list_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة التطبيقات"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    bot_state = load_bot_state()
    apps_list = bot_state.get('apps_list', [])
    
    if not apps_list:
        await update.message.reply_text("📭 لا توجد تطبيقات بعد")
        return
    
    text = "📱 **قائمة التطبيقات:**\n\n"
    for i, app in enumerate(apps_list[-10:], 1):  # آخر 10 تطبيقات
        text += f"{i}. **{app['name']}** - {app['version']} - {app['date']}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# تشغيل البوت
async def run_bot():
    logger.info("🚀 جاري تشغيل البوت...")
    
    bot_state = load_bot_state()
    logger.info(f"📊 آخر حالة: {bot_state.get('total_apps', 0)} تطبيق")
    logger.info(f"🔑 إجمالي الكودات: {len(load_codes().get('codes', {}))}")
    
    await init_userbot()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # معالج رسائل المجموعة للكودات
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code_request), group=1)
    
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
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(download_button, pattern="^download_"))
    app.add_handler(CallbackQueryHandler(code_button, pattern="^code_"))
    app.add_handler(CallbackQueryHandler(info_button, pattern="^info_"))
    app.add_handler(CallbackQueryHandler(back_button, pattern="^back_"))
    app.add_handler(CommandHandler('test', test))
    app.add_handler(CommandHandler('stats', stats))
    app.add_handler(CommandHandler('list', list_apps))
    
    logger.info("✅ البوت جاهز للعمل!")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        logger.info("🛑 جاري إيقاف البوت...")
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
