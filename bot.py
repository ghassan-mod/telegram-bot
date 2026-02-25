import os
import asyncio
import json
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

# ========== تشغيل يوزر بوت ==========
user_client = None

async def init_userbot():
    """تهيئة اليوزربوت بشكل صحيح"""
    global user_client
    try:
        logger.info("🔄 جاري تشغيل اليوزربوت...")
        
        if SESSION_STRING:
            # استخدام Session String
            user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
            await user_client.connect()
            logger.info("✅ يوزر بوت متصل باستخدام Session String")
        else:
            # تسجيل الدخول برقم الهاتف
            user_client = TelegramClient('user_session', API_ID, API_HASH)
            await user_client.start(phone=PHONE_NUMBER)
            logger.info("✅ يوزر بوت متصل باستخدام رقم الهاتف")
            # حفظ Session String
            session_str = user_client.session.save()
            logger.info(f"🔑 Session String: {session_str}")
        
        # التأكد من أن اليوزربوت شغال
        me = await user_client.get_me()
        logger.info(f"✅ يوزر بوت شغال كـ: {me.first_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ فشل تشغيل اليوزربوت: {e}")
        return False

async def ensure_userbot():
    """التأكد من أن اليوزربوت متصل"""
    global user_client
    try:
        if user_client is None:
            await init_userbot()
            return user_client is not None
        
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
            
            # تأكد من اتصال اليوزربوت
            if not await ensure_userbot():
                await update.message.reply_text("❌ مشكلة في الاتصال، حاول لاحقاً")
                return
            
            try:
                # إرسال الملف
                await user_client.send_file(
                    user.id,
                    app_info['file_id'],
                    caption=f"📥 **{app_info['name']}**\nشكراً لتحميلك التطبيق!"
                )
                
                # زيادة العداد
                app_info['downloads'] += 1
                save_downloads(downloads)
                
                await update.message.reply_text("✅ **تم التحميل بنجاح!**")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ خطأ: {str(e)[:100]}")
                logger.error(f"خطأ في التحميل: {e}")
                return
    
    # رسالة الترحيب
    welcome_text = (
        f"✨ مرحباً {user.first_name}!\n\n"
        "📱 **بوت رفع التطبيقات**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "🔹 ترقيم تلقائي (V1, V2, V3...)\n"
        "🔹 إضافة كود نسخة خاص\n"
        "🔹 عرض حجم التطبيق\n"
        "🔹 عداد تحميل دقيق\n"
        "🔹 إرسال مباشر من اليوزربوت\n"
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
        f"✅ **تم استلام الاسم**\n"
        f"📌 {app_name}\n\n"
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
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return PHOTO

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in app_data or 'name' not in app_data[user_id] or 'photo' not in app_data[user_id]:
        await update.message.reply_text("❌ حدث خطأ، الرجاء البدء من جديد")
        return ConversationHandler.END
    
    document = update.message.document
    if not document:
        await update.message.reply_text("❌ الرجاء إرسال ملف صالح")
        return FILE
    
    app_data[user_id]['file_id'] = document.file_id
    app_data[user_id]['file_name'] = document.file_name
    app_data[user_id]['file_size'] = document.file_size
    
    await update.message.reply_text(
        "🔢 **أرسل كود النسخة**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "مثال: 1.0.0\n\n"
        "📝 إذا لا يوجد كود، أرسل: **بدون**"
    )
    return VERSION_CODE

async def get_version_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    version_input = update.message.text
    
    if version_input.lower() in ['بدون', 'بدون كود', 'لا', 'none', 'no']:
        version_code = "بدون كود"
    else:
        version_code = version_input
    
    app_data[user_id]['version_code'] = version_code
    
    # استخراج البيانات
    app_name = app_data[user_id]['name']
    photo_id = app_data[user_id]['photo']
    file_id = app_data[user_id]['file_id']
    file_name = app_data[user_id]['file_name']
    file_size_bytes = app_data[user_id]['file_size']
    
    file_size = get_file_size(file_size_bytes)
    version_number = get_next_version()
    
    app_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # حفظ المعلومات
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
        'date': datetime.now().strftime('%Y-%m-%d'),
        'uploader': update.effective_user.mention_html(),
        'uploader_id': user_id
    }
    save_downloads(downloads)
    
    loading_msg = await update.message.reply_text("📤 **جاري النشر في القناة...**")
    
    try:
        # تحضير نص كود النسخة
        if version_code != "بدون كود":
            code_text = f"🔹 **كود النسخة:** `{version_code}`"
        else:
            code_text = "🔹 **كود النسخة:** بدون"
        
        # نص المنشور
        caption = (
            f"🚀 **{app_name}** | {version_number}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            f"📱 **تطبيق حصري** برعاية مطورينا!\n\n"
            f"⚡ **معلومات التطبيق:**\n"
            f"• الإصدار: {version_number}\n"
            f"• الحجم: {file_size}\n"
            f"{code_text}\n\n"
            f"💪 **لماذا هذا التطبيق؟**\n"
            f"✓ آمن 100% ومجرب\n"
            f"✓ تحديثات مستمرة\n"
            f"✓ دعم فني مباشر\n\n"
            f"👤 **المطور:** {update.effective_user.mention_html()}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            f"💬 **لتحميل التطبيق:** اضغط على زر التحميل أدناه"
        )
        
        # زر التحميل
        keyboard = [[
            InlineKeyboardButton(
                f"📥 تحميل التطبيق (0)", 
                callback_data=f"download_{app_id}"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال للقناة
        await context.bot.send_photo(
            chat_id=CHANNEL_USERNAME,
            photo=photo_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        await loading_msg.edit_text("✅ **تم النشر بنجاح!**")
        
        await update.message.reply_text(
            "🎉 **مبروك! تم رفع تطبيقك**\n\n"
            f"📌 الإصدار: {version_number}\n"
            f"📦 الحجم: {file_size}\n"
            f"🔢 الكود: {version_code}\n\n"
            f"🔗 {CHANNEL_USERNAME}"
        )
        
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ: {str(e)}")
        logger.error(f"خطأ في النشر: {e}")
    
    if user_id in app_data:
        del app_data[user_id]
    
    return ConversationHandler.END

# ========== هذا هو الجزء المهم - معالج التحميل الصحيح ==========
async def download_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج زر التحميل - مع التأكد من عمل كل شيء"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # رد سريع على الضغطة
    await query.answer("📦 جاري تجهيز الملف...")
    
    app_id = query.data.replace("download_", "")
    downloads = load_downloads()
    
    if app_id not in downloads:
        await query.edit_message_text("❌ التطبيق غير موجود")
        return
    
    app_info = downloads[app_id]
    
    # تغيير نص الزر مؤقتاً
    try:
        await query.edit_message_text(
            text=f"📦 **جاري التحميل...**\nسيتم إرسال {app_info['name']} إلى الخاص خلال لحظات"
        )
    except:
        pass
    
    try:
        # 1. التأكد من اتصال اليوزربوت
        logger.info(f"محاولة إرسال الملف للمستخدم {user_id}")
        
        if not await ensure_userbot():
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ عذراً، هناك مشكلة في الاتصال. حاول مرة أخرى لاحقاً."
            )
            return
        
        # 2. إرسال الملف عبر اليوزربوت
        await user_client.send_file(
            user_id,
            app_info['file_id'],
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
        
        logger.info(f"تم إرسال الملف بنجاح للمستخدم {user_id}")
        
        # 3. زيادة العداد
        app_info['downloads'] += 1
        save_downloads(downloads)
        logger.info(f"تم زيادة العداد إلى {app_info['downloads']}")
        
        # 4. تحديث الزر في القناة
        try:
            keyboard = [[
                InlineKeyboardButton(
                    f"📥 تحميل التطبيق ({app_info['downloads']})", 
                    callback_data=f"download_{app_id}"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # محاولة تحديث الرسالة الأصلية في القناة
            await query.message.edit_reply_markup(reply_markup=reply_markup)
            logger.info("تم تحديث الزر في القناة")
        except Exception as e:
            logger.warning(f"ماقدرتش أحدث الزر: {e}")
        
        # 5. إرسال تأكيد للمستخدم
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ **تم التحميل بنجاح!**\nتم إرسال {app_info['name']} إلى الخاص"
            )
        except:
            pass
        
        # 6. تحديث رسالة البوت
        try:
            await query.edit_message_text(
                text=f"✅ **تم التحميل بنجاح!**\nتم إرسال {app_info['name']} إلى الخاص"
            )
        except:
            pass
        
    except errors.FloodWaitError as e:
        await query.edit_message_text(f"⏳ التحميل مزدحم، انتظر {e.seconds} ثانية")
    except Exception as e:
        logger.error(f"خطأ في التحميل: {e}")
        await query.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}")
        
        # محاولة إعلام المستخدم
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ حدث خطأ في تحميل {app_info['name']}. حاول مرة أخرى."
            )
        except:
            pass

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    await update.message.reply_text("❌ تم إلغاء العملية.")
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذه الخاصية للمشرف فقط")
        return
    
    downloads = load_downloads()
    
    if not downloads:
        await update.message.reply_text("📊 لا توجد إحصائيات بعد")
        return
    
    total = sum(app['downloads'] for app in downloads.values())
    apps_count = len(downloads)
    
    stats_text = (
        f"📊 **إحصائيات التحميلات**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📱 عدد التطبيقات: {apps_count}\n"
        f"📥 إجمالي التحميلات: {total}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        f"**أكثر التطبيقات تحميلاً:**\n"
    )
    
    sorted_apps = sorted(downloads.items(), key=lambda x: x[1]['downloads'], reverse=True)[:5]
    
    for app_id, app_info in sorted_apps:
        stats_text += f"• {app_info['name']} ({app_info.get('version', 'V?')}): {app_info['downloads']} تحميل\n"
    
    await update.message.reply_text(stats_text)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذه الخاصية للمشرف فقط")
        return
    
    # اختبار اليوزربوت
    if await ensure_userbot():
        me = await user_client.get_me()
        await update.message.reply_text(f"✅ اليوزربوت يعمل كـ: {me.first_name}")
    else:
        await update.message.reply_text("❌ اليوزربوت لا يعمل")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📚 **مساعدة البوت**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "**الأوامر:**\n"
        "/start - بدء رفع تطبيق جديد\n"
        "/stats - الإحصائيات (للمشرف)\n"
        "/test - اختبار اليوزربوت (للمشرف)\n"
        "/help - هذه المساعدة\n"
        "/cancel - إلغاء العملية"
    )
    await update.message.reply_text(help_text)

# ========== تشغيل البوت ==========
async def run_bot():
    logger.info("🚀 جاري تشغيل البوت...")
    
    # تهيئة اليوزربوت
    await init_userbot()
    
    # تشغيل البوت
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
        logger.info("🛑 جاري إيقاف البوت...")
        await application.stop()
        if user_client:
            await user_client.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("👋 تم إيقاف البوت")
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {e}")
