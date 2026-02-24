import asyncio
import io
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# حالات المحادثة
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

# أمر البدء
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # إذا دخل من رابط تحميل
    if context.args and context.args[0].startswith('download_'):
        app_id = context.args[0]
        downloads = load_downloads()
        
        if app_id in downloads:
            app_info = downloads[app_id]
            try:
                # محاولة إرسال الملف بعد بدء المحادثة
                await context.bot.send_document(
                    chat_id=user.id,
                    document=app_info['file_id'],
                    filename=app_info['file_name'],
                    caption=f"📥 **تحميل {app_info['name']}**\nشكراً لتحميلك التطبيق!"
                )
                
                await update.message.reply_text(
                    "✅ **تم التحميل بنجاح!**\n"
                    "تم إرسال الملف لك في الخاص."
                )
                return
            except Exception as e:
                await update.message.reply_text(f"❌ حدث خطأ: {str(e)[:100]}")
                return
    
    # الوضع العادي للبدء
    welcome_text = (
        f"✨ مرحباً {user.first_name}!\n\n"
        "📱 **بوت رفع التطبيقات الاحترافي**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "🔹 سهل الاستخدام\n"
        "🔹 عداد تحميل تلقائي\n"
        "🔹 نشر احترافي في القناة\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        "👇 **أرسل اسم التطبيق** للبدء"
    )
    await update.message.reply_text(welcome_text)
    return NAME

# استقبال اسم التطبيق
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

# استقبال صورة التطبيق
async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    photo_file = await update.message.photo[-1].get_file()
    app_data[user_id]['photo'] = photo_file.file_id
    
    await update.message.reply_text(
        "✅ **تم استلام الصورة**\n\n"
        "📦 **أرسل ملف التطبيق الآن**\n"
        "(APK - IPA - ZIP)"
    )
    return FILE

# استقبال ملف التطبيق
async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel_id = -1002814161087  # قناة GSN-MOD
    
    if user_id not in app_data or 'name' not in app_data[user_id] or 'photo' not in app_data[user_id]:
        await update.message.reply_text("❌ حدث خطأ، الرجاء البدء من جديد باستخدام /start")
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
            f"💬 **كلمة للمتابعين:**\n"
            f"إذا عجبك التطبيق لا تنسى تشارك المنشور مع أصدقائك 👍\n"
            f"ودعماً للمطورين 👇 اضغط على زر التحميل"
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
            "🔗 @GSN_MOD\n\n"
            "📊 **عداد التحميلات يعمل تلقائياً**"
        )
        
    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ: {str(e)}")
    
    del app_data[user_id]
    return ConversationHandler.END

# معالج زر التحميل
async def download_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    app_id = query.data.replace("download_", "")
    downloads = load_downloads()
    
    if app_id in downloads:
        app_info = downloads[app_id]
        
        try:
            # محاولة إرسال الملف
            await context.bot.send_document(
                chat_id=user_id,
                document=app_info['file_id'],
                filename=app_info['file_name'],
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
            
            # إذا المستخدم ما بدأ محادثة مع البوت
            if "chat not found" in error or "bot can't initiate conversation" in error:
                bot_username = (await context.bot.get_me()).username
                start_link = f"https://t.me/{bot_username}?start=download_{app_id}"
                
                keyboard = [[
                    InlineKeyboardButton("🤖 اضغط هنا لبدء المحادثة", url=start_link)
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text="❌ **لا يمكن إرسال الملف**\n\n"
                         "عشان تحمل التطبيق، لازم تبدأ محادثة مع البوت أولاً.\n"
                         "اضغط على الزر تحت وبعدها ارجع اضغط على تحميل",
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}")
    else:
        await query.edit_message_text("❌ التطبيق غير موجود")

# إلغاء العملية
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in app_data:
        del app_data[user_id]
    
    await update.message.reply_text("❌ تم إلغاء العملية.")
    return ConversationHandler.END

# أمر الإحصائيات
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

# أمر اختبار القناة
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = -1002814161087
    
    try:
        await context.bot.send_message(
            chat_id=channel_id,
            text="✅ البوت يعمل على Render ويستقبل الأوامر!"
        )
        await update.message.reply_text("✅ تم إرسال رسالة اختبار للقناة")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {str(e)}")

# البرنامج الرئيسي
def main():
    TOKEN = "8666815258:AAHrMUXt9GdlRkld5cLoOu3qFCPXRYZOQIQ"
    
    application = Application.builder().token(TOKEN).build()
    
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
    
    print("✅ البوت الاحترافي يعمل...")
    print("⚡ في انتظار التطبيقات...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
