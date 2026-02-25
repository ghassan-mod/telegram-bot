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
NAME, PHOTO, FILE, VERSION_CODE = range(4)
app_data = {}
DOWNLOADS_FILE = "downloads_counter.json"
VERSION_COUNTER_FILE = "version_counter.json"

# التأكد من وجود مجلد temp
temp_dir = tempfile.gettempdir()
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# دوال المساعدة
def load_downloads():
    try:
        if os.path.exists(DOWNLOADS_FILE):
            with open(DOWNLOADS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في تحميل ملف التنزيلات: {e}")
    return {}

def save_downloads(downloads):
    try:
        with open(DOWNLOADS_FILE, 'w', encoding='utf-8') as f:
            json.dump(downloads, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ ملف التنزيلات: {e}")

def load_version_counter():
    try:
        if os.path.exists(VERSION_COUNTER_FILE):
            with open(VERSION_COUNTER_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('last_version', 0)
    except Exception as e:
        logger.error(f"خطأ في تحميل عداد الإصدارات: {e}")
    return 0

def save_version_counter(version):
    try:
        with open(VERSION_COUNTER_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_version': version}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ عداد الإصدارات: {e}")

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
        
        # التحقق من صحة الجلسة
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
    
    await update.message.reply_text("🔢 أرسل **كود النسخة** أو اكتب **بدون**")
    return VERSION_CODE

async def get_version_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    version = update.message.text
    if version.lower() in ['بدون', 'لا', 'none']:
        version = "بدون كود"
    
    data = app_data[user_id]
    version_num = get_next_version()
    app_id = f"app_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    downloads = load_downloads()
    downloads[app_id] = {
        'name': data['name'],
        'version': version_num,
        'version_code': version,
        'file_id': data['file_id'],
        'file_name': data['file_name'],
        'file_size': data['file_size'],
        'downloads': 0,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'uploader': update.effective_user.mention_html()
    }
    save_downloads(downloads)
    
    caption = (
        f"🚀 **{data['name']}** | {version_num}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📦 الحجم: {data['file_size']}\n"
        f"🔢 الكود: {version}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👤 {update.effective_user.mention_html()}"
    )
    
    keyboard = [[InlineKeyboardButton(f"📥 تحميل (0)", callback_data=f"download_{app_id}")]]
    
    await context.bot.send_photo(
        CHANNEL_USERNAME, 
        data['photo'], 
        caption,
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='HTML'
    )
    
    await update.message.reply_text(f"✅ تم النشر في {CHANNEL_USERNAME}")
    del app_data[user_id]
    return ConversationHandler.END

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
        # التحقق من اتصال اليوزربوت
        if not await ensure_userbot():
            await status_msg.edit_text("❌ مشكلة في الاتصال بالخادم، حاول مرة أخرى")
            return
        
        # تحميل الملف من تليجرام
        await status_msg.edit_text("📥 جاري تحميل الملف من الخادم...")
        file = await context.bot.get_file(app['file_id'])
        
        # إنشاء ملف مؤقت
        with tempfile.NamedTemporaryFile(delete=False, suffix='.apk') as tmp:
            path = tmp.name
        
        # تحميل الملف مع مهلة زمنية
        await status_msg.edit_text("📦 جاري تجهيز الملف للإرسال...")
        download_coro = file.download_to_drive(path)
        result = await download_with_timeout(download_coro, timeout=120)
        
        if result is None:
            await status_msg.edit_text("❌ فشل تحميل الملف (انتهت المهلة)")
            if os.path.exists(path):
                os.remove(path)
            return
        
        # إرسال الملف للمستخدم
        await status_msg.edit_text("📤 جاري إرسال الملف إلى الخاص...")
        await user_client.send_file(user_id, path, caption=f"📥 {app['name']} - {app['version']}")
        
        # حذف الملف المؤقت
        os.remove(path)
        
        # تحديث عداد التحميلات
        new_count = increment_download_count(app_id)
        
        # تحديث الزر في القناة
        try:
            keyboard = [[InlineKeyboardButton(f"📥 تحميل ({new_count})", callback_data=f"download_{app_id}")]]
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"خطأ في تحديث الزر: {e}")
        
        # تحديث رسالة الحالة
        await status_msg.edit_text(f"✅ تم إرسال {app['name']} إلى الخاص بنجاح!")
        
    except Exception as e:
        logger.error(f"خطأ في التحميل: {e}")
        try:
            await status_msg.edit_text("❌ حدث خطأ أثناء التحميل، حاول مرة أخرى")
        except:
            pass
        
        # تنظيف الملف المؤقت في حالة وجوده
        if 'path' in locals() and os.path.exists(path):
            os.remove(path)

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
            await status_msg.edit_text(
                f"✅ اليوزربوت شغال بنجاح!\n"
                f"👤 الاسم: {me.first_name}\n"
                f"🆔 المعرف: {me.id}"
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
    
    stats_text = (
        f"📊 إحصائيات البوت:\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📱 عدد التطبيقات: {total_apps}\n"
        f"📥 إجمالي التحميلات: {total_downloads}\n"
        f"🔄 آخر إصدار: {load_version_counter()}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
    )
    
    await update.message.reply_text(stats_text)

# تشغيل البوت
async def run_bot():
    logger.info("🚀 جاري تشغيل البوت...")
    
    # تهيئة اليوزربوت
    await init_userbot()
    
    # إعداد التطبيق
    app = Application.builder().token(BOT_TOKEN).build()
    
    # محادثة رفع التطبيقات
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            FILE: [MessageHandler(filters.Document.ALL, get_file)],
            VERSION_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_version_code)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # إضافة المعالجات
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(download_button, pattern="^download_"))
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
