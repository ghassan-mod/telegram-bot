import os
import asyncio
import json
import tempfile
from datetime import datetime
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
NAME, PHOTO, FILE, VERSION_CODE, DESCRIPTION = range(5)  # إضافة حالة جديدة للوصف
app_data = {}
DOWNLOADS_FILE = "downloads_counter.json"
VERSION_COUNTER_FILE = "version_counter.json"
BOT_STATE_FILE = "bot_state.json"  # ملف لحالة البوت

# التأكد من وجود مجلد temp
temp_dir = tempfile.gettempdir()
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# دوال المساعدة للحفظ والتحميل
def load_json_file(filename, default=None):
    """دالة عامة لتحميل ملفات JSON"""
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
    """دالة عامة لحفظ ملفات JSON"""
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
    """تحميل حالة البوت المحفوظة"""
    return load_json_file(BOT_STATE_FILE, {'last_app_id': None, 'total_apps': 0})

def save_bot_state(state):
    """حفظ حالة البوت"""
    save_json_file(BOT_STATE_FILE, state)

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

def generate_app_description(app_name, version, version_code, file_size):
    """توليد وصف احترافي للتطبيق"""
    descriptions = [
        f"""🔥 **{app_name} {version} – مخصوص للأجهزة الضعيفة!** 🔥

⚡️ لو جهازك ضعيف… ولا يهمك!
النسخة دي معمولة عشان تطيرك في اللعبة بدون لاج ولا تهنيج! 🚀

🎮 ثبات أكتر – لاج أقل – أداء خرافي للأجهزة الضعيفة
سيطر على اللعبة يا زعيم 💥😈

📦 **معلومات التطبيق:**
• الحجم: {file_size}
• الإصدار: {version}
• الكود: {version_code}

✅ **مضمونة 100%** – مجربة وشغالة بدون مشاكل
⚡️ **تحديث مستمر** – أحدث إصدار مع كل التحديثات""",

        f"""✨ **{app_name} {version} – الإصدار الذهبي!** ✨

🚀 **أسرع نسخة على الإطلاق** – مصممة خصيصاً للأداء العالي
🎯 **بدون أي تهنيج** – حتى على أضعف الأجهزة

💪 **مميزات حصريه:**
• ثبات في الإطارات FPS
• استهلاك أقل للرام
• بطارية تدوم أطول

📊 **التفاصيل:**
📦 الحجم: {file_size}
📌 الإصدار: {version}
🔢 الكود: {version_code}

🔥 **نضمنلك تجربة أسطورية** – حملها وجرب الفرق بنفسك!""",

        f"""⚡️ **{app_name} {version} – النسخة الخرافية** ⚡️

🎯 **صممت خصيصاً للمحترفين**
🏆 **أفضل أداء – أقل لاج – أسرع استجابة**

💎 **ليه تختار النسخة دي؟**
✓ تشتغل على كل الأجهزة
✓ تحديثات مستمرة
✓ دعم فني 24/7

📥 **التحميل مباشر وآمن**
📊 {file_size} – {version} – {version_code}

✅ **مجربة وآمنة 100%**
🌟 ثقة الآلاف من المستخدمين"""
    ]
    
    # اختيار وصف عشوائي
    import random
    return random.choice(descriptions)

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
    
    await update.message.reply_text("🔢 أرسل **كود النسخة** أو اكتب **بدون**")
    return VERSION_CODE

async def get_version_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    version = update.message.text
    if version.lower() in ['بدون', 'لا', 'none']:
        version = "بدون كود"
    
    app_data[user_id]['version_code'] = version
    
    # سؤال عن نوع الوصف المطلوب
    keyboard = [
        [InlineKeyboardButton("🔥 وصف قوي", callback_data="desc_strong")],
        [InlineKeyboardButton("✨ وصف احترافي", callback_data="desc_professional")],
        [InlineKeyboardButton("⚡️ وصف خرافي", callback_data="desc_amazing")],
        [InlineKeyboardButton("📝 كتابة وصف مخصص", callback_data="desc_custom")]
    ]
    
    await update.message.reply_text(
        "📝 **اختر نوع الوصف للتطبيق:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return DESCRIPTION

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
    description = generate_app_description(
        data['name'],
        get_next_version(),  # مؤقت، رح يتغير بعدين
        data['version_code'],
        data['file_size']
    )
    
    app_data[user_id]['description'] = description
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
    await update.message.reply_text("✅ تم حفظ الوصف، جاري النشر...")
    
    # متابعة النشر
    await publish_app(update, context, user_id)
    return ConversationHandler.END

async def publish_app(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """نشر التطبيق في القناة"""
    data = app_data[user_id]
    version_num = get_next_version()
    app_id = f"app_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # حفظ البيانات
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
        'uploader_name': update.effective_user.mention_html()
    }
    save_downloads(downloads)
    
    # تحديث حالة البوت
    bot_state = load_bot_state()
    bot_state['last_app_id'] = app_id
    bot_state['total_apps'] = len(downloads)
    save_bot_state(bot_state)
    
    # تجهيز الكيبورد
    keyboard = [
        [InlineKeyboardButton(f"📥 تحميل ({version_num})", callback_data=f"download_{app_id}")],
        [InlineKeyboardButton("📱 معلومات التطبيق", callback_data=f"info_{app_id}")]
    ]
    
    # إرسال للقناة
    await context.bot.send_photo(
        CHANNEL_USERNAME,
        data['photo'],
        caption=data['description'],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    await update.effective_user.send_message(f"✅ تم النشر بنجاح في {CHANNEL_USERNAME}!\n📱 الإصدار: {version_num}")
    del app_data[user_id]

# دالة التحميل المعدلة
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
    
    # إرسال رسالة منفصلة بدلاً من تعديل رسالة الزر
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
        
        # إرسال مع وصف احترافي
        caption = f"""✅ **{app['name']} {app['version']}**

📥 تم التحميل بنجاح
⚡️ استمتع بالتجربة
        
📊 {app['file_size']} | {app['version_code']}"""
        
        await user_client.send_file(user_id, path, caption=caption, parse_mode='Markdown')
        os.remove(path)
        
        # تحديث العداد
        new_count = increment_download_count(app_id)
        
        # تحديث الزر
        try:
            keyboard = [
                [InlineKeyboardButton(f"📥 تحميل ({new_count})", callback_data=f"download_{app_id}")],
                [InlineKeyboardButton("📱 معلومات التطبيق", callback_data=f"info_{app_id}")]
            ]
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
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
    
    info_text = f"""📱 **معلومات التطبيق**

**الاسم:** {app['name']}
**الإصدار:** {app['version']}
**كود الإصدار:** {app['version_code']}
**الحجم:** {app['file_size']}
**تاريخ الرفع:** {app['date']}
**مرات التحميل:** {app.get('downloads', 0)}
**رافع التطبيق:** {app.get('uploader_name', 'غير معروف')}

✅ **تطبيق آمن ومجرب 100%**"""
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"back_{app_id}")]]
    
    await query.edit_message_caption(
        caption=info_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
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
        keyboard = [
            [InlineKeyboardButton(f"📥 تحميل ({app.get('downloads', 0)})", callback_data=f"download_{app_id}")],
            [InlineKeyboardButton("📱 معلومات التطبيق", callback_data=f"info_{app_id}")]
        ]
        
        await query.edit_message_caption(
            caption=app['description'],
            reply_markup=InlineKeyboardMarkup(keyboard),
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
            
            await status_msg.edit_text(
                f"✅ **البوت يعمل بكفاءة!**\n\n"
                f"**اليوزربوت:** {me.first_name}\n"
                f"**آخر تطبيق:** {bot_state.get('last_app_id', 'لا يوجد')}\n"
                f"**إجمالي التطبيقات:** {bot_state.get('total_apps', 0)}\n"
                f"**آخر إصدار:** {load_version_counter()}",
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
    
    stats_text = (
        f"📊 **إحصائيات البوت**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📱 **عدد التطبيقات:** {total_apps}\n"
        f"📥 **إجمالي التحميلات:** {total_downloads}\n"
        f"🔄 **آخر إصدار:** {load_version_counter()}\n"
        f"💾 **آخر تطبيق:** {bot_state.get('last_app_id', 'لا يوجد')}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# تشغيل البوت
async def run_bot():
    logger.info("🚀 جاري تشغيل البوت...")
    
    # تحميل الحالة السابقة
    bot_state = load_bot_state()
    logger.info(f"📊 آخر حالة: {bot_state}")
    
    # تهيئة اليوزربوت
    await init_userbot()
    
    # إعداد التطبيق
    app = Application.builder().token(BOT_TOKEN).build()
    
    # محادثة رفع التطبيقات مع الوصف
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            FILE: [MessageHandler(filters.Document.ALL, get_file)],
            VERSION_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_version_code)],
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
    app.add_handler(CallbackQueryHandler(info_button, pattern="^info_"))
    app.add_handler(CallbackQueryHandler(back_button, pattern="^back_"))
    app.add_handler(CommandHandler('test', test))
    app.add_handler(CommandHandler('stats', stats))
    
    # تشغيل البوت
    logger.info("✅ البوت جاهز للعمل!")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # البقاء قيد التشغيل
    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        logger.info("🛑 جاري إيقاف البوت...")
        # حفظ الحالة قبل الإيقاف
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
