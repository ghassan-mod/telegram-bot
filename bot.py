import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# ========== البيانات ==========
API_ID = 39458857
API_HASH = "3b62c284e0f6b6b0b16ba6d7b46a4a6f"
BOT_TOKEN = "8666815258:AAHrMUXt9GdlRkld5cLoOu3qFCPXRYZOQIQ"
PHONE_NUMBER = "967735264023"
ADMIN_ID = 1972494449
CHANNEL_USERNAME = "@GSN_MOD"  # معرف القناة
SESSION_STRING = "1BJWap1sBu3zgU7WP5-n2wRQTSuJduN7DNxzIdfM2e_4FptGKHvUbrWfsynuMt_fbmC_Qmh68fKP5fEujloHTo_c5e4dlzornqDQxzPGlQn1J9W4tp9Qsu66w7BZiOC3_D4Gh1-wRzUoRp-7tjZUiSvT0z3J6rX3vwR6lBb2Ntq_rni9kMNTuLSjiAZVkSpFAIBxfM8JxCS1qeAGyx5IY6OlP4goEyXyOPGVcYvXsTpeN2IPhikwDnMWSF0tvRlyjHaRGNTkc1_XmXs8HibQWZtW7cAClnLYeHAcXP3MgfToVzSwXRwnnFUCA_oxDVkMzeJFkERIdKDVUaAfktmQazeoLprdoY-I="

# ========== إعدادات ==========
# حالات المحادثة للبوت العادي
NAME, PHOTO, FILE = range(3)

# بيانات مؤقتة للتطبيق
app_data = {}

# ملف لحفظ عدد التحميلات
DOWNLOADS_FILE = "downloads_counter.json"

# تحميل عداد التحميلات
def load_downloads():
    if os.path.exists(DOWNLOADS_FILE):
        with open(DOWNLOADS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# حفظ عداد التحميلات
def save_downloads(downloads):
    with open(DOWNLOADS_FILE, 'w', encoding='utf-8') as f:
        json.dump(downloads, f, ensure_ascii=False, indent=2)

# ========== تشغيل Telethon (يوزر بوت) ==========
user_client = TelegramClient('user_session', API_ID, API_HASH)

async def start_userbot():
    """تشغيل يوزر بوت"""
    try:
        if SESSION_STRING:
            await user_client.start(bot_token=BOT_TOKEN)  # جرب كبوت أولاً
            print("✅ يوزر بوت شغال كبوت")
        else:
            await user_client.start(phone=PHONE_NUMBER)
            print("✅ يوزر بوت شغال كمستخدم")
    except:
        try:
            await user_client.start(phone=PHONE_NUMBER)
            print("✅ يوزر بوت شغال كمستخدم")
        except Exception as e:
            print(f"❌ فشل تشغيل يوزر بوت: {e}")
    
    # استقبال الأوامر من القناة (للتأكد)
    @user_client.on(events.NewMessage(chats=CHANNEL_USERNAME))
    async def handler(event):
        print(f"📨 رسالة جديدة في القناة: {event.message.text[:50]}")

# ========== دوال البوت العادي (PTB) ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if context.args and context.args[0].startswith('download_'):
        app_id = context.args[0]
        downloads = load_downloads()
        
        if app_id in downloads:
            app_info = downloads[app_id]
            try:
                # محاولة إرسال الملف عن طريق يوزر بوت (مايحتاج start)
                await user_client.send_file(
                    user.id,
                    app_info['file_id'],
                    caption=f"📥 **تحميل {app_info['name']}**\nشكراً لتحميلك التطبيق!"
                )
                
                await update.message.reply_text("✅ **تم التحميل بنجاح!**")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ حدث خطأ: {str(e)[:100]}")
                return
    
    welcome_text = (
        f"✨ مرحباً {user.first_name}!\n\n"
        "📱 **بوت رفع التطبيقات**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "🔹 سهل الاستخدام\n"
        "🔹 عداد تحميل تلقائي\n"
        "🔹 إرسال عن طريق يوزر بوت\n"
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
    
    photo_file = await update.message.photo[-1].get_file()
    app_data[user_id]['photo'] = photo_file.file_id
    
    await update.message.reply_text(
        "✅ **تم استلام الصورة**\n\n"
        "📦 **أرسل ملف التطبيق الآن**"
    )
    return FILE

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel_id = int(os.environ.get('CHANNEL_ID', -1002814161087))
    
    if user_id not in app_data or 'name' not in app_data[user_id] or 'photo' not in app_data[user_id]:
        await update.message.reply_text("❌ حدث خطأ، الرجاء البدء من جديد")
        return ConversationHandler.END
    
    app_name = app_data[user_id]['name']
    photo_id = app_data[user_id]['photo']
    
    document = update.message.document
    if not document:
        await update.message.reply_text("❌ الرجاء إرسال ملف صالح")
        return FILE
    
    app_id = f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    file_id = document.file_id
    file_name = document.file_name
    
    downloads = load_downloads()
    downloads[app_id] = {
        'name': app_name,
        'file_id': file_id,
        'file_name': file_name,
        'downloads': 0,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'uploader': update.effective_user.mention_html()
    }
    save_downloads(downloads)
    
    loading_msg = await update.message.reply_text("📤 **جاري النشر في القناة...**")
    
    try:
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
        
        bot_username = (await context.bot.get_me()).username
        start_link = f"https://t.me/{bot_username}?start=download_{app_id}"
        
        keyboard = [[
            InlineKeyboardButton(
                f"📥 تحميل التطبيق (0)", 
                callback_data=f"download_{app_id}"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال للقناة عن طريق البوت العادي
        await context.bot.send_photo(
            chat_id=channel_id,
            photo=photo_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        await loading_msg.edit_text("✅ **تم النشر بنجاح!**")
        
        await update.message.reply_text(
            "🎉 **مبروك! تم رفع تطبيقك**\n\n"
            "✅ أصبح التطبيق الآن في القناة\n"
            f"🔗 {CHANNEL_USERNAME}\n\n"
            "📊 **عداد التحميلات يعمل تلقائياً**"
        )
        
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ: {str(e)}")
    
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
            # ✅ إرسال الملف عن طريق يوزر بوت (ما يحتاج المستخدم يضغط start)
            await user_client.send_file(
                user_id,
                app_info['file_id'],
                caption=f"📥 **تحميل {app_info['name']}**\nشكراً لتحميلك التطبيق!"
            )
            
            # زيادة العداد
            app_info['downloads'] += 1
            save_downloads(downloads)
            
            # تحديث الزر
            keyboard = [[
                InlineKeyboardButton(
                    f"📥 تحميل التطبيق ({app_info['downloads']})", 
                    callback_data=f"download_{app_id}"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_reply_markup(reply_markup=reply_markup)
            
            await query.edit_message_text(
                text=f"✅ **تم التحميل بنجاح!**\nتم إرسال الملف في الخاص",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            error = str(e).lower()
            await query.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}")
    else:
        await query.edit_message_text("❌ التطبيق غير موجود")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    
    await update.message.reply_text("❌ تم إلغاء العملية.")
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    channel_id = int(os.environ.get('CHANNEL_ID', -1002814161087))
    
    try:
        await context.bot.send_message(
            chat_id=channel_id,
            text="✅ البوت يعمل ويستخدم يوزر بوت للإرسال!"
        )
        await update.message.reply_text("✅ تم إرسال رسالة اختبار للقناة")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")

# ========== تشغيل البوتين معاً ==========
async def run_bot():
    """تشغيل البوت العادي ويوزر بوت معاً"""
    # تشغيل يوزر بوت
    asyncio.create_task(start_userbot())
    
    # تشغيل البوت العادي
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            FILE: [MessageHandler(filters.Document.ALL, get_file)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(download_button, pattern="^download_"))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('test', test))
    
    print("✅ البوت العادي يعمل...")
    print("✅ يوزر بوت يعمل...")
    print("⚡ في انتظار التطبيقات...")
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # البقاء قيد التشغيل
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(run_bot())
