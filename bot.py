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
required_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'PHONE_NUMBER', 'ADMIN_ID', 'CHANNEL_USERNAME']
missing_vars = [var for var in required_vars if not os.environ.get(var)]

if missing_vars:
    logger.error(f"❌ المتغيرات التالية غير موجودة: {', '.join(missing_vars)}")
    exit(1)

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

def format_app_caption(app_info, uploader_mention):
    version_code_text = f"🔢 **كود النسخة:** `{app_info['version_code']}`" if app_info['version_code'] != "بدون كود" else "🔢 **كود النسخة:** بدون"
    
    caption = (
        f"🚀 **{app_info['name']}** | {app_info['version']}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        f"📱 **تطبيق حصري** برعاية مطورينا!\n\n"
        f"⚡ **معلومات التطبيق:**\n"
        f"• الإصدار: {app_info['version']}\n"
        f"• الحجم: {app_info['file_size']}\n"
        f"{version_code_text}\n\n"
        f"💪 **لماذا هذا التطبيق؟**\n"
        f"✓ آمن 100% ومجرب\n"
        f"✓ تحديثات مستمرة\n"
        f"✓ دعم فني مباشر\n"
        f"✓ جودة عالية وأداء ممتاز\n\n"
        f"👤 **المطور:** {uploader_mention}\n"
        f"📅 **التاريخ:** {app_info['date']}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        f"💬 **لتحميل التطبيق:** اضغط على زر التحميل أدناه"
    )
    return caption

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
        
        me = await user_client.get_me()
        logger.info(f"✅ تم تسجيل الدخول بنجاح كـ: {me.first_name}")
        return True
        
    except errors.SessionPasswordNeededError:
        logger.error("❌ المصادقة الثنائية مفعلة")
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

# ========== دوال البوت الرئيسية ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if context.args and context.args[0].startswith('download_'):
        app_id = context.args[0]
        downloads = load_downloads()
        
        if app_id in downloads:
            app_info = downloads[app_id]
            
            if not await ensure_userbot():
                await update.message.reply_text("❌ مشكلة في الاتصال")
                return
            
            try:
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
        "📱 **بوت رفع التطبيقات الاحترافي**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "**✨ المميزات:**\n"
        "✅ ترقيم تلقائي (V1, V2, V3...)\n"
        "✅ إضافة كود نسخة خاص قابل للنسخ\n"
        "✅ عرض حجم التطبيق بدقة\n"
        "✅ عداد تحميل دقيق ومتجدد\n"
        "✅ إرسال مباشر من اليوزربوت\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "📌 **خطوات الرفع:**\n"
        "1️⃣ أرسل **اسم التطبيق**\n"
        "2️⃣ أرسل **صورة التطبيق**\n"
        "3️⃣ أرسل **ملف التطبيق**\n"
        "4️⃣ أرسل **كود النسخة**\n\n"
        "👇 **أرسل اسم التطبيق الآن**"
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
        f"📦 حجم الملف: {app_data[user_id]['file_size']}"
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
    file_size_bytes = app_data[user_id]['file_size_bytes']
    
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
        'file_size_bytes': file_size_bytes,
        'downloads': 0,
        'date': current_date,
        'uploader': uploader_mention,
        'uploader_id': user_id
    }
    save_downloads(downloads)
    
    loading_msg = await update.message.reply_text("📤 **جاري النشر في القناة...**")
    
    try:
        caption = format_app_caption(downloads[app_id], uploader_mention)
        
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
        
        success_message = (
            f"🎉 **تم الرفع بنجاح!**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📌 الإصدار: {version_number}\n"
            f"📦 الحجم: {file_size}\n"
            f"🔢 الكود: {version_code}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📢 القناة: {CHANNEL_USERNAME}"
        )
        await update.message.reply_text(success_message)
        
        if user_id != ADMIN_ID:
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"📦 تطبيق جديد: {app_name} - {version_number}",
                    parse_mode='HTML'
                )
            except:
                pass
        
    except Exception as e:
        await loading_msg.edit_text(f"❌ خطأ: {str(e)}")
        logger.error(f"خطأ في النشر: {e}")
    
    if user_id in app_data:
        del app_data[user_id]
    
    return ConversationHandler.END

# ========== دالة التحميل الأهم ==========
async def download_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج زر التحميل - إرسال الملف عبر اليوزربوت"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer("📦 جاري تجهيز الملف...")
    
    app_id = query.data.replace("download_", "")
    downloads = load_downloads()
    
    if app_id not in downloads:
        await query.edit_message_text("❌ التطبيق غير موجود")
        return
    
    app_info = downloads[app_id]
    
    # رسالة انتظار
    try:
        await query.edit_message_text(
            text=f"📦 **جاري التحميل...**\nسيتم إرسال {app_info['name']} خلال لحظات"
        )
    except:
        pass
    
    try:
        # التأكد من اتصال اليوزربوت
        if not await ensure_userbot():
            await context.bot.send_message(user_id, "❌ مشكلة في الاتصال")
            return
        
        # ===== الطريقة المضمونة 100% =====
        # 1. تحميل الملف من سيرفرات تلغرام
        file = await context.bot.get_file(app_info['file_id'])
        
        # 2. إنشاء ملف مؤقت
        file_ext = os.path.splitext(app_info.get('file_name', 'file.apk'))[1]
        if not file_ext:
            file_ext = '.apk'
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            file_path = tmp_file.name
        
        # 3. تحميل الملف
        await file.download_to_drive(file_path)
        
        # 4. إرسال الملف عبر اليوزربوت
        await user_client.send_file(
            user_id,
            file_path,
            caption=(
                f"📥 **{app_info['name']}**\n"
                f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
                f"📌 الإصدار: {app_info.get('version', 'V1')}\n"
                f"📦 الحجم: {app_info.get('file_size', 'غير معروف')}\n"
                f"🔢 الكود: {app_info.get('version_code', 'بدون')}\n"
                f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
                f"شكراً لتحميلك التطبيق! ❤️"
            ),
            parse_mode='markdown'
        )
        
        # 5. حذف الملف المؤقت
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 6. زيادة العداد
        app_info['downloads'] += 1
        save_downloads(downloads)
        
        # 7. تحديث الزر في القناة
        try:
            keyboard = [[
                InlineKeyboardButton(
                    f"📥 تحميل التطبيق ({app_info['downloads']})", 
                    callback_data=f"download_{app_id}"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_reply_markup(reply_markup=reply_markup)
        except:
            pass
        
        # 8. تأكيد للمستخدم
        try:
            await context.bot.send_message(
                user_id,
                f"✅ **تم التحميل بنجاح!**\nتم إرسال {app_info['name']} إلى الخاص"
            )
        except:
            pass
        
        try:
            await query.edit_message_text(
                f"✅ **تم التحميل بنجاح!**\nتم إرسال {app_info['name']} إلى الخاص"
            )
        except:
            pass
        
        logger.info(f"✅ تم إرسال {app_info['name']} للمستخدم {user_id}")
        
    except errors.FloodWaitError as e:
        await query.edit_message_text(f"⏳ انتظر {e.seconds} ثانية")
    except Exception as e:
        logger.error(f"خطأ في التحميل: {e}")
        try:
            await query.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}")
        except:
            pass

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
    
    stats_text = (
        f"📊 **الإحصائيات**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📱 عدد التطبيقات: {apps_count}\n"
        f"📥 إجمالي التحميلات: {total}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        f"**الأكثر تحميلاً:**\n"
    )
    
    sorted_apps = sorted(downloads.items(), key=lambda x: x[1]['downloads'], reverse=True)[:5]
    
    for i, (app_id, app_info) in enumerate(sorted_apps, 1):
        stats_text += f"{i}. {app_info['name']}: {app_info['downloads']}\n"
    
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
        "📚 **المساعدة**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "/start - رفع تطبيق\n"
        "/stats - الإحصائيات (مشرف)\n"
        "/test - الفحص (مشرف)\n"
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
