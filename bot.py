import os
import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import logging
import tempfile

# ========== إعدادات التسجيل (Logging) ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== قراءة المتغيرات من Railway ==========
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
NAME, PHOTO, FILE, VERSION_CODE = range(4)
app_data = {}
DOWNLOADS_FILE = "downloads_counter.json"
VERSION_COUNTER_FILE = "version_counter.json"

# ========== دوال المساعدة (Helper Functions) ==========

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

def load_version_counter():
    """تحميل عداد الإصدارات من ملف JSON"""
    try:
        if os.path.exists(VERSION_COUNTER_FILE):
            with open(VERSION_COUNTER_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('last_version', 0)
    except Exception as e:
        logger.error(f"خطأ في تحميل عداد الإصدارات: {e}")
    return 0

def save_version_counter(version):
    """حفظ عداد الإصدارات في ملف JSON"""
    try:
        with open(VERSION_COUNTER_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_version': version}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ عداد الإصدارات: {e}")

def get_next_version():
    """الحصول على رقم الإصدار التالي (V1, V2, V3...)"""
    current = load_version_counter()
    next_version = current + 1
    save_version_counter(next_version)
    return f"V{next_version}"

def get_file_size(file_size_bytes):
    """تحويل حجم الملف إلى صيغة مفهومة (KB, MB, GB)"""
    if file_size_bytes < 1024 * 1024:
        return f"{file_size_bytes / 1024:.1f} KB"
    elif file_size_bytes < 1024 * 1024 * 1024:
        return f"{file_size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{file_size_bytes / (1024 * 1024 * 1024):.1f} GB"

def format_app_caption(app_info, uploader_mention):
    """تنسيق نص المنشور بشكل احترافي"""
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

# ========== تشغيل يوزر بوت (Telethon) ==========
user_client = None

async def init_userbot():
    """تهيئة اليوزربوت بشكل صحيح"""
    global user_client
    try:
        logger.info("🔄 جاري تشغيل اليوزربوت...")
        
        if SESSION_STRING:
            # استخدام Session String إذا كان موجوداً
            user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
            await user_client.connect()
            logger.info("✅ يوزر بوت متصل باستخدام Session String")
        else:
            # تسجيل الدخول برقم الهاتف
            user_client = TelegramClient('user_session', API_ID, API_HASH)
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

async def ensure_userbot():
    """التأكد من اتصال اليوزربوت"""
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

# ========== دوال البوت الرئيسية (Bot Handlers) ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية المحادثة مع البوت"""
    user = update.effective_user
    
    # إذا دخل من رابط تحميل (من القناة)
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
                # محاولة إرسال الملف
                await user_client.send_file(
                    user.id,
                    app_info['file_id'],
                    caption=f"📥 **{app_info['name']}**\nشكراً لتحميلك التطبيق!"
                )
                
                # زيادة العداد
                app_info['downloads'] += 1
                save_downloads(downloads)
                
                await update.message.reply_text("✅ **تم التحميل بنجاح!** تم إرسال الملف في الخاص")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ حدث خطأ في التحميل: {str(e)[:100]}")
                logger.error(f"خطأ في التحميل: {e}")
                return
    
    # رسالة الترحيب المحسنة
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
        "✅ وصف احترافي للتطبيق\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "📌 **خطوات الرفع:**\n"
        "1️⃣ أرسل **اسم التطبيق**\n"
        "2️⃣ أرسل **صورة التطبيق**\n"
        "3️⃣ أرسل **ملف التطبيق** (APK)\n"
        "4️⃣ أرسل **كود النسخة** (مثال: 1.0.0)\n\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "👇 **أرسل اسم التطبيق الآن** للبدء"
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
        f"✅ **تم استلام الاسم بنجاح**\n"
        f"📌 **اسم التطبيق:** {app_name}\n\n"
        "🖼 **الخطوة التالية:** أرسل صورة التطبيق الآن"
    )
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام صورة التطبيق"""
    user_id = update.effective_user.id
    
    try:
        # أخذ أعلى جودة للصورة
        photo_file = await update.message.photo[-1].get_file()
        app_data[user_id]['photo'] = photo_file.file_id
        
        await update.message.reply_text(
            "✅ **تم استلام الصورة بنجاح**\n\n"
            "📦 **الخطوة التالية:** أرسل ملف التطبيق (APK, ZIP)\n"
            "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            "📌 سيتم عرض حجم الملف تلقائياً"
        )
        return FILE
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return PHOTO

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام ملف التطبيق"""
    user_id = update.effective_user.id
    
    # التحقق من البيانات السابقة
    if user_id not in app_data or 'name' not in app_data[user_id] or 'photo' not in app_data[user_id]:
        await update.message.reply_text("❌ حدث خطأ، الرجاء البدء من جديد باستخدام /start")
        return ConversationHandler.END
    
    document = update.message.document
    if not document:
        await update.message.reply_text("❌ الرجاء إرسال ملف صالح (APK, ZIP, إلخ)")
        return FILE
    
    # حفظ معلومات الملف
    app_data[user_id]['file_id'] = document.file_id
    app_data[user_id]['file_name'] = document.file_name
    app_data[user_id]['file_size_bytes'] = document.file_size
    app_data[user_id]['file_size'] = get_file_size(document.file_size)
    
    # طلب كود النسخة
    await update.message.reply_text(
        "🔢 **أرسل كود النسخة**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "📌 مثال: `1.0.0` أو `2.5`\n"
        "📌 إذا لا يوجد كود، أرسل: **بدون**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📦 حجم الملف: {app_data[user_id]['file_size']}"
    )
    return VERSION_CODE

async def get_version_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استلام كود النسخة ونشر التطبيق"""
    user_id = update.effective_user.id
    version_input = update.message.text
    
    # التحقق من البيانات
    if user_id not in app_data:
        await update.message.reply_text("❌ حدث خطأ، الرجاء البدء من جديد")
        return ConversationHandler.END
    
    # تحديد كود النسخة
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
    file_size = app_data[user_id]['file_size']
    file_size_bytes = app_data[user_id]['file_size_bytes']
    
    # الحصول على رقم الإصدار التالي
    version_number = get_next_version()
    
    # إنشاء معرف فريد للتطبيق
    app_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    current_date = datetime.now().strftime('%Y-%m-%d')
    uploader_mention = update.effective_user.mention_html()
    
    # حفظ معلومات التطبيق في ملف التحميلات
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
        # تنسيق نص المنشور
        caption = format_app_caption(downloads[app_id], uploader_mention)
        
        # إنشاء زر التحميل
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
        
        await loading_msg.edit_text("✅ **تم النشر في القناة بنجاح!**")
        
        # رسالة التأكيد للمستخدم
        success_message = (
            f"🎉 **تم رفع التطبيق بنجاح!** 🎉\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📌 **الإصدار:** {version_number}\n"
            f"📦 **الحجم:** {file_size}\n"
            f"🔢 **الكود:** {version_code}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📢 **القناة:** {CHANNEL_USERNAME}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"✅ عداد التحميلات يعمل تلقائياً"
        )
        await update.message.reply_text(success_message)
        
        # إشعار المشرف
        if user_id != ADMIN_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"📦 **تطبيق جديد:**\nالاسم: {app_name}\nالإصدار: {version_number}\nبواسطة: {uploader_mention}",
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
    """معالج زر التحميل - إرسال الملف عبر اليوزربوت"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer("📦 جاري تجهيز الملف...")
    
    app_id = query.data.replace("download_", "")
    downloads = load_downloads()
    
    if app_id not in downloads:
        await query.edit_message_text("❌ التطبيق غير موجود أو تم حذفه")
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
        # التأكد من اتصال اليوزربوت
        logger.info(f"محاولة إرسال الملف للمستخدم {user_id}")
        
        if not await ensure_userbot():
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ عذراً، هناك مشكلة في الاتصال. حاول مرة أخرى لاحقاً."
            )
            return
        
        # محاولة إرسال الملف - مع خطة بديلة
        try:
            # المحاولة الأولى: إرسال مباشر باستخدام file_id
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
            logger.info(f"تم إرسال الملف مباشرة للمستخدم {user_id}")
            
        except Exception as e:
            # إذا فشل الإرسال المباشر، نجرب طريقة بديلة
            logger.warning(f"فشل الإرسال المباشر، جرب الطريقة البديلة: {e}")
            
            # تحميل الملف من البوت ثم إرساله
            file = await context.bot.get_file(app_info['file_id'])
            
            # إنشاء ملف مؤقت
            with tempfile.NamedTemporaryFile(delete=False, suffix='.apk') as tmp_file:
                file_path = tmp_file.name
            
            # تحميل الملف
            await file.download_to_drive(file_path)
            
            # إرسال الملف المحمل
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
            
            # حذف الملف المؤقت
            if os.path.exists(file_path):
                os.remove(file_path)
            
            logger.info(f"تم إرسال الملف عبر الطريقة البديلة للمستخدم {user_id}")
        
        # زيادة عداد التحميلات
        app_info['downloads'] += 1
        save_downloads(downloads)
        logger.info(f"تم زيادة العداد إلى {app_info['downloads']}")
        
        # تحديث الزر في القناة
        try:
            keyboard = [[
                InlineKeyboardButton(
                    f"📥 تحميل التطبيق ({app_info['downloads']})", 
                    callback_data=f"download_{app_id}"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # محاولة تحديث رسالة القناة
            await query.message.edit_reply_markup(reply_markup=reply_markup)
            logger.info("تم تحديث الزر في القناة")
        except Exception as e:
            logger.warning(f"ماقدرتش أحدث الزر: {e}")
        
        # إرسال تأكيد للمستخدم
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ **تم التحميل بنجاح!**\nتم إرسال {app_info['name']} إلى الخاص"
            )
        except:
            pass
        
        # تحديث رسالة البوت
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
        
        try:
            await query.edit_message_text(
                text=f"❌ حدث خطأ في التحميل. حاول مرة أخرى."
            )
        except:
            pass

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية الحالية"""
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    
    await update.message.reply_text(
        "❌ **تم إلغاء العملية**\n"
        "يمكنك البدء من جديد باستخدام /start"
    )
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
        f"**🏆 أكثر التطبيقات تحميلاً:**\n"
    )
    
    sorted_apps = sorted(downloads.items(), key=lambda x: x[1]['downloads'], reverse=True)[:5]
    
    for i, (app_id, app_info) in enumerate(sorted_apps, 1):
        stats_text += f"{i}. {app_info['name']} ({app_info.get('version', 'V?')}): {app_info['downloads']} تحميل\n"
    
    await update.message.reply_text(stats_text)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار البوت واليوزربوت"""
    # التحقق من أن المستخدم هو المشرف
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذه الخاصية للمشرف فقط")
        return
    
    status_text = "🔍 **فحص البوت:**\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    
    # اختبار البوت العادي
    try:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="✅ البوت العادي يعمل بشكل طبيعي"
        )
        status_text += "✅ البوت العادي: يعمل\n"
    except:
        status_text += "❌ البوت العادي: لا يعمل\n"
    
    # اختبار اليوزربوت
    if await ensure_userbot():
        me = await user_client.get_me()
        status_text += f"✅ اليوزربوت: يعمل كـ {me.first_name}\n"
    else:
        status_text += "❌ اليوزربوت: لا يعمل\n"
    
    # اختبار القناة
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text="✅ البوت يعمل ويستخدم يوزر بوت للإرسال!"
        )
        status_text += f"✅ القناة {CHANNEL_USERNAME}: متاحة\n"
    except:
        status_text += f"❌ القناة {CHANNEL_USERNAME}: غير متاحة\n"
    
    await update.message.reply_text(status_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة"""
    help_text = (
        "📚 **مساعدة البوت**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "**الأوامر المتاحة:**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "/start - بدء رفع تطبيق جديد\n"
        "/stats - عرض الإحصائيات (للمشرف فقط)\n"
        "/test - اختبار البوت (للمشرف فقط)\n"
        "/help - عرض هذه المساعدة\n"
        "/cancel - إلغاء العملية الحالية\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "**📱 كيفية رفع تطبيق:**\n"
        "1️⃣ أرسل /start\n"
        "2️⃣ أرسل اسم التطبيق\n"
        "3️⃣ أرسل صورة التطبيق\n"
        "4️⃣ أرسل ملف التطبيق (APK)\n"
        "5️⃣ أرسل كود النسخة (مثال: 1.0.0)\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "✅ سيتم نشر التطبيق في القناة تلقائياً مع:\n"
        "• رقم إصدار تلقائي (V1, V2...)\n"
        "• حجم التطبيق\n"
        "• كود النسخة (قابل للنسخ)"
    )
    await update.message.reply_text(help_text)

# ========== تشغيل البوت ==========
async def run_bot():
    """تشغيل البوت العادي ويوزر بوت معاً"""
    logger.info("🚀 جاري تشغيل البوت...")
    
    # تهيئة اليوزربوت
    userbot_status = await init_userbot()
    if not userbot_status:
        logger.warning("⚠️ اليوزربوت لم يعمل بشكل صحيح، بعض الميزات قد لا تعمل")
    
    # انتظر قليلاً
    await asyncio.sleep(2)
    
    # تشغيل البوت العادي
    application = Application.builder().token(BOT_TOKEN).build()
    
    # معالج المحادثة الرئيسي
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
    
    # إضافة جميع المعالجات
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
        if user_client:
            await user_client.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("👋 تم إيقاف البوت")
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {e}")
