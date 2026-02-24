import os
import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, events
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ========== قراءة المتغيرات ==========
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PHONE_NUMBER = os.environ.get('PHONE_NUMBER', '')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME', '@GSN_MOD')
SESSION_STRING = os.environ.get('SESSION_STRING', '')

# التأكد من أن معرف القناة صحيح
if not CHANNEL_USERNAME.startswith('@'):
    CHANNEL_USERNAME = '@' + CHANNEL_USERNAME

# ========== إعدادات البوت ==========
NAME, PHOTO, FILE = range(3)
app_data = {}
DOWNLOADS_FILE = "downloads_counter.json"

# تحميل وحفظ عداد التحميلات
def load_downloads():
    if os.path.exists(DOWNLOADS_FILE):
        with open(DOWNLOADS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_downloads(downloads):
    with open(DOWNLOADS_FILE, 'w', encoding='utf-8') as f:
        json.dump(downloads, f, ensure_ascii=False, indent=2)

# ========== تشغيل يوزر بوت ==========
user_client = TelegramClient('user_session', API_ID, API_HASH)

async def start_userbot():
    """تشغيل يوزر بوت للإرسال المباشر"""
    try:
        if SESSION_STRING:
            # استخدام session string إذا كان موجوداً
            from telethon.sessions import StringSession
            session = StringSession(SESSION_STRING)
            user_client = TelegramClient(session, API_ID, API_HASH)
            await user_client.start()
            print("✅ يوزر بوت شغال باستخدام الجلسة المحفوظة")
        else:
            # تسجيل الدخول برقم الهاتف
            await user_client.start(phone=PHONE_NUMBER)
            # حفظ الجلسة للاستخدام المستقبلي
            session_str = user_client.session.save()
            print(f"🔑 احفظ هذه الجلسة: {session_str}")
            print("✅ يوزر بوت شغال كمستخدم")
            
    except Exception as e:
        print(f"❌ فشل تشغيل يوزر بوت: {e}")

# ========== دوال البوت العادي ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # إذا دخل من رابط تحميل
    if context.args and context.args[0].startswith('download_'):
        app_id = context.args[0]
        downloads = load_downloads()
        
        if app_id in downloads:
            app_info = downloads[app_id]
            try:
                # محاولة إرسال الملف عن طريق البوت العادي أولاً
                await context.bot.send_document(
                    chat_id=user.id,
                    document=app_info['file_id'],
                    caption=f"📥 **تحميل {app_info['name']}**"
                )
                await update.message.reply_text("✅ تم التحميل بنجاح!")
                return
            except Exception as e:
                # إذا فشل، أعطه رابط يبدأ المحادثة
                bot_username = (await context.bot.get_me()).username
                start_link = f"https://t.me/{bot_username}?start=download_{app_id}"
                await update.message.reply_text(
                    f"❌ عشان تحمل، اضغط على الرابط أولاً:\n{start_link}"
                )
                return
    
    welcome = (
        f"✨ مرحباً {user.first_name}!\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "📱 أرسل اسم التطبيق للبدء:"
    )
    await update.message.reply_text(welcome)
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    app_name = update.message.text
    
    app_data[user_id] = {'name': app_name}
    
    await update.message.reply_text("✅ تم حفظ الاسم\n🖼 أرسل صورة التطبيق:")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    photo = await update.message.photo[-1].get_file()
    app_data[user_id]['photo'] = photo.file_id
    
    await update.message.reply_text("✅ تم حفظ الصورة\n📦 أرسل ملف التطبيق:")
    return FILE

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in app_data or 'name' not in app_data[user_id] or 'photo' not in app_data[user_id]:
        await update.message.reply_text("❌ خطأ، أرسل /start مرة أخرى")
        return ConversationHandler.END
    
    app_name = app_data[user_id]['name']
    photo_id = app_data[user_id]['photo']
    document = update.message.document
    
    if not document:
        await update.message.reply_text("❌ أرسل ملف صالح")
        return FILE
    
    # حفظ المعلومات
    app_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    downloads = load_downloads()
    downloads[app_id] = {
        'name': app_name,
        'file_id': document.file_id,
        'file_name': document.file_name,
        'downloads': 0,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'uploader_id': user_id
    }
    save_downloads(downloads)
    
    # إنشاء زر التحميل
    keyboard = [[
        InlineKeyboardButton(
            f"📥 تحميل (0)", 
            callback_data=f"down_{app_id}"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # إرسال للقناة
    try:
        caption = (
            f"🚀 **{app_name}**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
            f"👤 بواسطة: {update.effective_user.first_name}"
        )
        
        await context.bot.send_photo(
            chat_id=CHANNEL_USERNAME,
            photo=photo_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        await update.message.reply_text("✅ تم النشر في القناة!")
        
    except Exception as e:
        await update.message.reply_text(f"❌ فشل النشر: {str(e)}")
    
    # تنظيف
    del app_data[user_id]
    return ConversationHandler.END

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج زر التحميل"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    app_id = query.data.replace("down_", "")
    downloads = load_downloads()
    
    if app_id not in downloads:
        await query.edit_message_text("❌ التطبيق غير موجود")
        return
    
    app_info = downloads[app_id]
    
    # محاولة إرسال الملف
    try:
        # أولاً: محاولة الإرسال عن طريق البوت
        await context.bot.send_document(
            chat_id=user_id,
            document=app_info['file_id'],
            caption=f"📥 **{app_info['name']}**"
        )
        
        # زيادة العداد
        app_info['downloads'] += 1
        save_downloads(downloads)
        
        # تحديث الزر
        try:
            new_keyboard = [[
                InlineKeyboardButton(
                    f"📥 تحميل ({app_info['downloads']})", 
                    callback_data=f"down_{app_id}"
                )
            ]]
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(new_keyboard)
            )
        except:
            pass  # إذا فشل التحديث، تجاهل
        
        # إرسال رسالة تأكيد خاصة
        await context.bot.send_message(
            chat_id=user_id,
            text="✅ تم التحميل بنجاح!"
        )
        
    except Exception as e:
        # إذا فشل، أعطه رابط البداية
        bot_username = (await context.bot.get_me()).username
        start_link = f"https://t.me/{bot_username}?start=download_{app_id}"
        
        await query.edit_message_text(
            text=f"❌ عشان تحمل، اضغط على الرابط أولاً:\n{start_link}",
            reply_markup=None
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    await update.message.reply_text("✅ تم الإلغاء")
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات التحميلات"""
    downloads = load_downloads()
    
    if not downloads:
        await update.message.reply_text("📊 لا توجد إحصائيات")
        return
    
    total = sum(d['downloads'] for d in downloads.values())
    apps_count = len(downloads)
    
    stats_text = (
        f"📊 **الإحصائيات**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📱 التطبيقات: {apps_count}\n"
        f"📥 التحميلات: {total}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        f"**الأكثر تحميلاً:**\n"
    )
    
    sorted_apps = sorted(downloads.items(), key=lambda x: x[1]['downloads'], reverse=True)[:3]
    for app_id, info in sorted_apps:
        stats_text += f"• {info['name']}: {info['downloads']}\n"
    
    await update.message.reply_text(stats_text)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار القناة"""
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text="✅ البوت شغال!"
        )
        await update.message.reply_text("✅ القناة شغالة")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")

# ========== تشغيل البوت ==========
async def run_bot():
    """تشغيل البوت"""
    # تشغيل يوزر بوت في الخلفية
    asyncio.create_task(start_userbot())
    
    # تشغيل البوت العادي
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            FILE: [MessageHandler(filters.Document.ALL, get_file)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(download_handler, pattern="^down_"))
    app.add_handler(CommandHandler('stats', stats))
    app.add_handler(CommandHandler('test', test))
    
    print("✅ البوت شغال...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # البقاء قيد التشغيل
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(run_bot())
