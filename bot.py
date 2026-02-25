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

# ========== إعدادات التسجيل ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== قراءة المتغيرات ==========
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PHONE_NUMBER = os.environ.get('PHONE_NUMBER')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME')
SESSION_STRING = os.environ.get('SESSION_STRING', '')

if not CHANNEL_USERNAME.startswith('@'):
    CHANNEL_USERNAME = '@' + CHANNEL_USERNAME

# ========== إعدادات البوت ==========
NAME, PHOTO, FILE, VERSION_CODE = range(4)
app_data = {}
DOWNLOADS_FILE = "downloads_counter.json"
VERSION_COUNTER_FILE = "version_counter.json"

# ========== دوال المساعدة ==========
def load_downloads():
    try:
        if os.path.exists(DOWNLOADS_FILE):
            with open(DOWNLOADS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في تحميل التحميلات: {e}")
    return {}

def save_downloads(downloads):
    try:
        with open(DOWNLOADS_FILE, 'w', encoding='utf-8') as f:
            json.dump(downloads, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ التحميلات: {e}")

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

def get_file_size(file_size_bytes):
    if file_size_bytes < 1024 * 1024:
        return f"{file_size_bytes / 1024:.1f} KB"
    elif file_size_bytes < 1024 * 1024 * 1024:
        return f"{file_size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{file_size_bytes / (1024 * 1024 * 1024):.1f} GB"

# ========== تشغيل يوزر بوت ==========
user_client = None

async def init_userbot():
    global user_client
    try:
        logger.info("🔄 جاري تشغيل اليوزربوت...")
        
        if SESSION_STRING:
            user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
            await user_client.connect()
            logger.info("✅ يوزر بوت متصل باستخدام Session String")
        else:
            user_client = TelegramClient('user_session', API_ID, API_HASH)
            await user_client.start(phone=PHONE_NUMBER)
            logger.info("✅ يوزر بوت متصل باستخدام رقم الهاتف")
            session_str = user_client.session.save()
            logger.info(f"🔑 Session String الخاص بك: {session_str}")
            logger.info("📝 انسخ هذا الكود وحطه في متغير SESSION_STRING")
        
        me = await user_client.get_me()
        logger.info(f"✅ تم تسجيل الدخول بنجاح كـ: {me.first_name}")
        return True
        
    except errors.SessionPasswordNeededError:
        logger.error("❌ المصادقة الثنائية مفعلة - عطلها من إعدادات تلغرام")
        return False
    except Exception as e:
        logger.error(f"❌ فشل تشغيل يوزر بوت: {e}")
        return False

async def ensure_userbot():
    global user_client
    try:
        if user_client is None:
            return await init_userbot()
        
        if not user_client.is_connected():
            await user_client.connect()
        
        if not await user_client.is_user_authorized():
            if SESSION_STRING:
                user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
                await user_client.connect()
            else:
                await user_client.start(phone=PHONE_NUMBER)
        
        return True
    except Exception as e:
        logger.error(f"خطأ في التأكد من اتصال اليوزربوت: {e}")
        return False

# ========== دوال البوت ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # إذا دخل من رابط تحميل
    if context.args and context.args[0].startswith('download_'):
        app_id = context.args[0]
        downloads = load_downloads()
        
        if app_id in downloads:
            app_info = downloads[app_id]
            
            if not await ensure_userbot():
                await update.message.reply_text("❌ مشكلة في الاتصال")
                return
            
            try:
                # محاولة إرسال الملف
                await user_client.send_file(
                    user.id,
                    app_info['file_id'],
                    caption=f"📥 **{app_info['name']}**\nشكراً لتحميلك التطبيق!"
                )
                app_info['downloads'] += 1
                save_downloads(downloads)
                await update.message.reply_text("✅ تم التحميل بنجاح!")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ خطأ: {str(e)[:100]}")
                return
    
    welcome_text = (
        f"✨ **مرحباً {user.first_name}!** ✨\n\n"
        "📱 **بوت رفع التطبيقات**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "**المميزات:**\n"
        "✅ ترقيم تلقائي (V1, V2, V3...)\n"
        "✅ إضافة كود نسخة\n"
        "✅ عرض حجم التطبيق\n"
        "✅ عداد تحميل دقيق\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "👇 **أرسل اسم التطبيق** للبدء"
    )
    await update.message.reply_text(welcome_text)
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    app_name = update.message.text
    user_id = update.effective_user.id
    
    if user_id not in app_data:
        app_data[user_id] = {}
    app_data[user_id]['name'] = app_name
    
    await update.message.reply_text(
        f"✅ **تم استلام الاسم:** {app_name}\n\n"
        "🖼 **أرسل صورة التطبيق الآن**"
    )
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        app_data[user_id]['photo'] = photo_file.file_id
        
        await update.message.reply_text(
            "✅ **تم استلام الصورة**\n\n"
            "📦 **أرسل ملف التطبيق الآن**"
        )
        return FILE
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")
        return PHOTO

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in app_data or 'name' not in app_data[user_id] or 'photo' not in app_data[user_id]:
        await update.message.reply_text("❌ حدث خطأ، استخدم /start")
        return ConversationHandler.END
    
    document = update.message.document
    if not document:
        await update.message.reply_text("❌ أرسل ملف صالح")
        return FILE
    
    app_data[user_id]['file_id'] = document.file_id
    app_data[user_id]['file_name'] = document.file_name
    app_data[user_id]['file_size_bytes'] = document.file_size
    app_data[user_id]['file_size'] = get_file_size(document.file_size)
    
    await update.message.reply_text(
        f"🔢 **أرسل كود النسخة**\n"
        f"مثال: `1.0.0` أو اكتب **بدون**\n\n"
        f"📦 الحجم: {app_data[user_id]['file_size']}"
    )
    return VERSION_CODE

async def get_version_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    version_input = update.message.text
    
    if user_id not in app_data:
        await update.message.reply_text("❌ خطأ، استخدم /start")
        return ConversationHandler.END
    
    version_code = "بدون كود" if version_input.lower() in ['بدون', 'بدون كود', 'لا', 'none'] else version_input
    app_data[user_id]['version_code'] = version_code
    
    app_name = app_data[user_id]['name']
    photo_id = app_data[user_id]['photo']
    file_id = app_data[user_id]['file_id']
    file_name = app_data[user_id]['file_name']
    file_size = app_data[user_id]['file_size']
    
    version_number = get_next_version()
    app_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    current_date = datetime.now().strftime('%Y-%m-%d')
    uploader_mention = update.effective_user.mention_html()
    
    downloads = load_downloads()
    downloads[app_id] = {
        'name': app_name,
        'version': version_number,
        'version_code': version_code,
        'file_id': file_id,
        'file_name': file_name,
        'file_size': file_size,
        'downloads': 0,
        'date': current_date,
        'uploader': uploader_mention
    }
    save_downloads(downloads)
    
    loading_msg = await update.message.reply_text("📤 **جاري النشر في القناة...**")
    
    try:
        version_code_text = f"🔢 **كود النسخة:** `{version_code}`" if version_code != "بدون كود" else "🔢 **كود النسخة:** بدون"
        
        caption = (
            f"🚀 **{app_name}** | {version_number}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            f"📱 **تطبيق حصري**\n\n"
            f"⚡ **المعلومات:**\n"
            f"• الإصدار: {version_number}\n"
            f"• الحجم: {file_size}\n"
            f"{version_code_text}\n\n"
            f"👤 **المطور:** {uploader_mention}\n"
            f"📅 **التاريخ:** {current_date}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            f"💬 اضغط على زر التحميل"
        )
        
        keyboard = [[
            InlineKeyboardButton(
                f"📥 تحميل التطبيق (0)", 
                callback_data=f"download_{app_id}"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_photo(
            chat_id=CHANNEL_USERNAME,
            photo=photo_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        await loading_msg.edit_text("✅ **تم النشر بنجاح!**")
        
        await update.message.reply_text(
            f"🎉 **تم الرفع!**\n"
            f"📌 الإصدار: {version_number}\n"
            f"📢 القناة: {CHANNEL_USERNAME}"
        )
        
    except Exception as e:
        await loading_msg.edit_text(f"❌ خطأ: {str(e)}")
        logger.error(f"خطأ في النشر: {e}")
    
    if user_id in app_data:
        del app_data[user_id]
    
    return ConversationHandler.END

# ========== دالة التحميل المضمونة 100% ==========
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
    
    await query.edit_message_text(f"📦 جاري تجهيز {app['name']}...")
    
    try:
        # 1. نتأكد من اتصال اليوزربوت
        if not await ensure_userbot():
            await context.bot.send_message(user_id, "❌ مشكلة في الاتصال")
            return
        
        # 2. نجيب الملف من البوت
        file = await context.bot.get_file(app['file_id'])
        
        # 3. ننشئ ملف مؤقت
        with tempfile.NamedTemporaryFile(delete=False, suffix='.apk') as tmp:
            file_path = tmp.name
        
        # 4. نحمل الملف
        await file.download_to_drive(file_path)
        
        # 5. نرسله عبر اليوزربوت
        await user_client.send_file(
            user_id,
            file_path,
            caption=f"📥 {app['name']}\nشكراً لتحميلك! ❤️"
        )
        
        # 6. نحذف الملف المؤقت
        os.remove(file_path)
        
        # 7. نزيد العداد
        app['downloads'] += 1
        save_downloads(downloads)
        
        # 8. نحدث الزر في القناة
        try:
            keyboard = [[
                InlineKeyboardButton(
                    f"📥 تحميل ({app['downloads']})", 
                    callback_data=f"download_{app_id}"
                )
            ]]
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass
        
        # 9. نرسل تأكيد
        await query.edit_message_text(f"✅ تم إرسال {app['name']} إلى الخاص")
        await context.bot.send_message(user_id, f"✅ تم إرسال {app['name']} إلى الخاص")
        
    except Exception as e:
        logger.error(f"خطأ في التحميل: {e}")
        await query.edit_message_text("❌ حدث خطأ في التحميل")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ للمشرف فقط")
        return
    
    downloads = load_downloads()
    
    if not downloads:
        await update.message.reply_text("📊 لا توجد إحصائيات")
        return
    
    total = sum(app['downloads'] for app in downloads.values())
    apps_count = len(downloads)
    
    stats_text = f"📊 إجمالي التحميلات: {total}\nعدد التطبيقات: {apps_count}\n\n"
    
    for app_id, app_info in list(downloads.items())[:5]:
        stats_text += f"• {app_info['name']}: {app_info['downloads']}\n"
    
    await update.message.reply_text(stats_text)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ للمشرف فقط")
        return
    
    status = "🔍 **الفحص:**\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    
    try:
        await context.bot.send_message(update.effective_user.id, "✅ البوت يعمل")
        status += "✅ البوت العادي: يعمل\n"
    except:
        status += "❌ البوت العادي: لا يعمل\n"
    
    if await ensure_userbot():
        me = await user_client.get_me()
        status += f"✅ اليوزربوت: يعمل ({me.first_name})\n"
    else:
        status += "❌ اليوزربوت: لا يعمل\n"
    
    try:
        await context.bot.send_message(CHANNEL_USERNAME, "✅ اختبار القناة")
        status += f"✅ القناة: متاحة\n"
    except:
        status += f"❌ القناة: غير متاحة\n"
    
    await update.message.reply_text(status)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "/start - رفع تطبيق\n"
        "/stats - الإحصائيات\n"
        "/test - فحص البوت\n"
        "/help - المساعدة\n"
        "/cancel - إلغاء"
    )
    await update.message.reply_text(help_text)

# ========== تشغيل البوت ==========
async def run_bot():
    logger.info("🚀 جاري التشغيل...")
    
    await init_userbot()
    await asyncio.sleep(2)
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            FILE: [MessageHandler(filters.Document.ALL, get_file)],
            VERSION_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_version_code)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(download_button, pattern="^download_"))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('test', test))
    application.add_handler(CommandHandler('help', help_command))
    
    logger.info("✅ البوت يعمل...")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        logger.info("🛑 إيقاف...")
        await application.stop()
        if user_client:
            await user_client.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("👋 تم الإيقاف")
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
