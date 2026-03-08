import telebot
import json
import os

TOKEN = os.environ.get('TOKEN', 'PUT_YOUR_TOKEN_HERE')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 1972494449))

bot = telebot.TeleBot(TOKEN)

# تحميل التطبيقات
def load_apps():
    try:
        with open("apps.json","r") as f:
            return json.load(f)
    except:
        return []

# حفظ التطبيقات
def save_apps(app):
    apps = load_apps()
    apps.append(app)
    with open("apps.json","w") as f:
        json.dump(apps,f,indent=4)

# البداية
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == ADMIN_ID:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📤 رفع نسخة","📦 عرض التطبيقات")
        bot.send_message(message.chat.id,"لوحة المطور",reply_markup=markup)
    else:
        show_apps(message.chat.id)

# عرض التطبيقات للمستخدمين
def show_apps(chat_id):
    apps = load_apps()
    if not apps:
        bot.send_message(chat_id,"لا يوجد تطبيقات بعد")
        return
    for app in apps:
        markup = telebot.types.InlineKeyboardMarkup()
        btn = telebot.types.InlineKeyboardButton("⬇️ تحميل",url=app["link"])
        markup.add(btn)
        bot.send_photo(
            chat_id,
            app["photo"],
            caption=app["name"],
            reply_markup=markup
        )

# زر عرض التطبيقات للمطور
@bot.message_handler(func=lambda m: m.text=="📦 عرض التطبيقات")
def view_apps(message):
    show_apps(message.chat.id)

# زر رفع نسخة للمطور
@bot.message_handler(func=lambda m: m.text=="📤 رفع نسخة")
def upload(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id,"📷 ارسل صورة التطبيق")
    bot.register_next_step_handler(msg,get_photo)

def get_photo(message):
    if not message.photo:
        msg = bot.send_message(message.chat.id,"ارسل صورة فقط")
        bot.register_next_step_handler(msg,get_photo)
        return
    photo = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id,"📝 اكتب اسم التطبيق")
    bot.register_next_step_handler(msg,get_name,photo)

def get_name(message,photo):
    name = message.text
    msg = bot.send_message(message.chat.id,"🔗 ارسل رابط التحميل")
    bot.register_next_step_handler(msg,get_link,name,photo)

def get_link(message,name,photo):
    link = message.text
    app = {
        "name":name,
        "photo":photo,
        "link":link
    }
    save_apps(app)
    bot.send_message(message.chat.id,"✅ تم رفع التطبيق")

bot.infinity_polling()
