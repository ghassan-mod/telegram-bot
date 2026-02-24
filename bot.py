import os
import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, errors
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import logging

# ========== إعدادات التسجيل (Logging) ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== قراءة المتغيرات من Railway ==========
# التحقق من وجود المتغيرات
required_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'PHONE_NUMBER', 'ADMIN_ID', 'CHANNEL_USERNAME']
missing_vars = [var for var in required_vars if not os.environ.get(var)]

if missing_vars:
    logger.error(f"❌ المتغيرات التالية غير موجودة: {', '.join(missing_vars)}")
    logger.error("يرجى إضافتها في إعدادات Railway")
    exit(1)

API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PHONE_NUMBER = os.environ.get('PHONE_NUMBER')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME')
SESSION_STRING = os.environ.get('SESSION_STRING', '')

# التأكد من أن CHANNEL_USERNAME يبدأ بـ @
if not CHANNEL_USERNAME.startswith('@'):
    CHANNEL_USERNAME = '@' + CHANNEL_USERNAME

# ========== إعدادات البوت ==========
NAME, PHOTO, FILE = range(3)
app_data = {}
DOWNLOADS_FILE = "downloads_counter.json"
SESSION_FILE = "user_session.session"

# تحميل وحفظ عداد التحميلات
def load_downloads():
    """تحميل عداد التحميلات من ملف JSON"""
    try:
        if os.path.exists(DOWNLOADS_FILE):
            with open(DOWNLOADS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"خطأ في تحميل التحميلات: {e}")
    return {}

def save_downloads(downloads):
    """حفظ عداد التحميلات في ملف JSON"""
    try:
        with open(DOWNLOADS_FILE, 'w', encoding='utf-8') as f:
            json.dump(downloads, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ التحميلات: {e}")

# ========== تشغيل يوزر بوت (Telethon) ==========
user_client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

async def start_userbot():
    """تشغيل يوزر بوت للإرسال المباشر"""
    try:
        logger.info("🔄 جاري تشغيل اليوزربوت...")
        
        if SESSION_STRING:
            # استخدام Session String إذا كان موجوداً
            from telethon.sessions import StringSession
            user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
            await user_client.connect()
            logger.info("✅ يوزر بوت متصل باستخدام Session String")
        else:
            # تسجيل الدخول برقم الهاتف
            await user_client.start(phone=PHONE_NUMBER)
            logger.info("✅ يوزر بوت متصل باستخدام رقم الهاتف")
            
            # حفظ Session String للاستخدام المستقبلي
            session_str = user_client.session.save()
            logger.info(f"🔑 Session String الخاص بك: {session_str}")
            logger.info("📝 احفظ هذا الكود في متغير SESSION_STRING للاستخدام المستقبلي")
        
        # التأكد من أن اليوزربوت يعمل
        me = await user_client.get_me()
        logger.info(f"✅ تم تسجيل الدخول بنجاح كـ: {me.first_name} (@{me.username})")
        
        return True
        
    except errors.SessionPasswordNeededError:
        logger.error("❌ المصادقة الثنائية مفعلة. يرجى تعطيلها أو إضافة كلمة المرور")
        return False
    except Exception as e:
        logger.error(f"❌ فشل تشغيل يوزر بوت: {e}")
        return False

# ========== دوال البوت العادي ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية المحادثة مع البوت"""
    user = update.effective_user
    
    # إذا دخل من رابط تحميل
    if context.args and context.args[0].startswith('download_'):
        app_id = context.args[0]
        downloads = load_downloads()
        
        if app_id in downloads:
            app_info = downloads[app_id]
            try:
                # التأكد من أن اليوزربوت متصل
                if not user_client.is_connected():
                    await start_userbot()
                
                # إرسال الملف عن طريق يوزر بوت
                await user_client.send_file(
                    user.id,
                    app_info['file_id'],
                    caption=f"📥 **{app_info['name']}**\nشكراً لتحميلك التطبيق!",
                    parse_mode='markdown'
                )
                await update.message.reply_text("✅ **تم التحميل بنجاح!** تم إرسال الملف في الخاص")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ حدث خطأ في التحميل: {str(e)[:100]}")
                logger.error(f"خطأ في التحميل: {e}")
                return
    
    # رسالة الترحيب
    welcome_text = (
        f"✨ مرحباً {user.first_name}!\n\n"
        "📱 **بوت رفع التطبيقات**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "🔹 سهل الاستخدام\n"
        "🔹 عداد تحميل تلقائي\n"
        "🔹 إرسال مباشر بدون Start\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "👇 **أرسل اسم التطبيق** للبدء"
    )
    await update.message.reply_text(welcome_text)
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام اسم التطبيق"""
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
    """استلام صورة التطبيق"""
    user_id = update.effective_user.id
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        app_data[user_id]['photo'] = photo_file.file_id
        
        await update.message.reply_text(
            "✅ **تم استلام الصورة**\n\n"
            "📦 **أرسل ملف التطبيق الآن**\n"
            "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            "🔹 ملف APK أو أي صيغة أخرى"
        )
        return FILE
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return PHOTO

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام ملف التطبيق ونشره في القناة"""
    user_id = update.effective_user.id
    
    # التحقق من البيانات
    if user_id not in app_data or 'name' not in app_data[user_id] or 'photo' not in app_data[user_id]:
        await update.message.reply_text("❌ حدث خطأ، الرجاء البدء من جديد باستخدام /start")
        return ConversationHandler.END
    
    app_name = app_data[user_id]['name']
    photo_id = app_data[user_id]['photo']
    
    document = update.message.document
    if not document:
        await update.message.reply_text("❌ الرجاء إرسال ملف صالح (APK, ZIP, إلخ)")
        return FILE
    
    # إنشاء معرف فريد للتطبيق
    app_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    file_id = document.file_id
    file_name = document.file_name
    
    # حفظ معلومات التطبيق
    downloads = load_downloads()
    downloads[app_id] = {
        'name': app_name,
        'file_id': file_id,
        'file_name': file_name,
        'downloads': 0,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'uploader': update.effective_user.mention_html(),
        'uploader_id': user_id
    }
    save_downloads(downloads)
    
    loading_msg = await update.message.reply_text("📤 **جاري النشر في القناة...**")
    
    try:
        # نص المنشور
        caption = (
            f"🚀 **{app_name}**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            f"📱 **تطبيق حصري** تم رفعه بواسطة مطورينا!\n\n"
            f"✨ **مميزات التطبيق:**\n"
            f"• نسخة محدثة وآمنة\n"
            f"• خفيف وسريع\n"
            f"• متوافق مع جميع الأجهزة\n\n"
            f"👤 **المطور:** {update.effective_user.mention_html()}\n"
            f"📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d')}\n"
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
            "✅ أصبح التطبيق الآن في القناة\n"
            f"🔗 {CHANNEL_USERNAME}\n\n"
            "📊 **عداد التحميلات يعمل تلقائياً**"
        )
        
        # إشعار المشرف
        if user_id != ADMIN_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"📦 تطبيق جديد:\nالاسم: {app_name}\nبواسطة: {update.effective_user.mention_html()}",
                    parse_mode='HTML'
                )
            except:
                pass
        
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ في النشر: {str(e)}")
        logger.error(f"خطأ في نشر التطبيق: {e}")
    
    # تنظيف البيانات
    if user_id in app_data:
        del app_data[user_id]
    
    return ConversationHandler.END

async def download_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج زر التحميل - يستخدم يوزر بوت للإرسال"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    app_id = query.data.replace("download_", "")
    downloads = load_downloads()
    
    if app_id in downloads:
        app_info = downloads[app_id]
        
        try:
            # التأكد من أن اليوزربوت متصل
            if not user_client.is_connected():
                await start_userbot()
            
            # إرسال الملف عن طريق يوزر بوت
            await user_client.send_file(
                user_id,
                app_info['file_id'],
                caption=f"📥 **{app_info['name']}**\nشكراً لتحميلك التطبيق!",
                parse_mode='markdown'
            )
            
            # زيادة العداد
            app_info['downloads'] += 1
            save_downloads(downloads)
            
            # تحديث الزر في القناة
            try:
                keyboard = [[
                    InlineKeyboardButton(
                        f"📥 تحميل التطبيق ({app_info['downloads']})", 
                        callback_data=f"download_{app_id}"
                    )
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_reply_markup(reply_markup=reply_markup)
            except Exception as e:
                logger.warning(f"لا يمكن تحديث الزر: {e}")
            
            # إرسال رسالة تأكيد للمستخدم
            await query.edit_message_text(
                text=f"✅ **تم التحميل بنجاح!**\nتم إرسال {app_info['name']} إلى الخاص",
                reply_markup=None
            )
            
        except errors.FloodWaitError as e:
            # خطأ التكرار - انتظر ثم حاول
            await query.edit_message_text(f"⏳ التحميل مزدحم، انتظر {e.seconds} ثانية")
        except Exception as e:
            await query.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}")
            logger.error(f"خطأ في التحميل: {e}")
    else:
        await query.edit_message_text("❌ التطبيق غير موجود أو تم حذفه")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية"""
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    
    await update.message.reply_text("❌ تم إلغاء العملية.")
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات التحميلات"""
    # التحقق من أن المستخدم هو المشرف
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
        stats_text += f"• {app_info['name']}: {app_info['downloads']} تحميل\n"
    
    await update.message.reply_text(stats_text)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار البوت والقناة"""
    # التحقق من أن المستخدم هو المشرف
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذه الخاصية للمشرف فقط")
        return
    
    try:
        # اختبار البوت
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="✅ البوت يعمل بشكل طبيعي"
        )
        
        # اختبار القناة
        await context.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text="✅ البوت يعمل ويستخدم يوزر بوت للإرسال!"
        )
        
        # اختبار اليوزربوت
        if user_client.is_connected():
            me = await user_client.get_me()
            await update.message.reply_text(f"✅ اليوزربوت يعمل كـ: {me.first_name}")
        else:
            await update.message.reply_text("⚠️ اليوزربوت غير متصل، جاري التشغيل...")
            await start_userbot()
        
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض مساعدة"""
    help_text = (
        "📚 **مساعدة البوت**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "**الأوامر المتاحة:**\n"
        "/start - بدء رفع تطبيق جديد\n"
        "/stats - عرض الإحصائيات (للمشرف فقط)\n"
        "/test - اختبار البوت (للمشرف فقط)\n"
        "/help - عرض هذه المساعدة\n"
        "/cancel - إلغاء العملية الحالية\n\n"
        "**كيفية الرفع:**\n"
        "1️⃣ أرسل /start\n"
        "2️⃣ أرسل اسم التطبيق\n"
        "3️⃣ أرسل صورة التطبيق\n"
        "4️⃣ أرسل ملف التطبيق\n\n"
        "✅ سيتم نشر التطبيق في القناة تلقائياً"
    )
    await update.message.reply_text(help_text)

# ========== تشغيل البوتين معاً ==========
async def run_bot():
    """تشغيل البوت العادي ويوزر بوت معاً"""
    logger.info("🚀 جاري تشغيل البوت...")
    
    # تشغيل يوزر بوت
    userbot_status = await start_userbot()
    if not userbot_status:
        logger.warning("⚠️ اليوزربوت لم يعمل بشكل صحيح، بعض الميزات قد لا تعمل")
    
    # انتظر قليلاً
    await asyncio.sleep(2)
    
    # تشغيل البوت العادي
    application = Application.builder().token(BOT_TOKEN).build()
    
    # معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            FILE: [MessageHandler(filters.Document.ALL, get_file)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # إضافة المعالجات
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(download_button, pattern="^download_"))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('test', test))
    application.add_handler(CommandHandler('help', help_command))
    
    logger.info("✅ البوت العادي يعمل...")
    logger.info("⚡ في انتظار التطبيقات...")
    
    # تشغيل البوت
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # البقاء قيد التشغيل
    try:
        await asyncio.Future()  # انتظر للأبد
    except KeyboardInterrupt:
        logger.info("🛑 جاري إيقاف البوت...")
        await application.stop()
        await user_client.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("👋 تم إيقاف البوت")
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {e}")
