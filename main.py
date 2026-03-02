import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# قراءة التوكن من Environment Variables
TOKEN = os.getenv("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📥 تحميل النسخة", url="https://t.me/GSN_MOD")],
        [InlineKeyboardButton("🎥 يوتيوب", url="https://youtube.com/@gsn-mod")],
        [InlineKeyboardButton("📢 قناة تيليجرام", url="https://t.me/GSN_MOD")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("أهلاً بك في بوت GSN_MOD 👋 اختر من القائمة:", reply_markup=reply_markup)

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()
