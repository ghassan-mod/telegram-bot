import os
import json
import feedparser
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask
import threading

# إعداد logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# المتغيرات الأساسية
TOKEN = os.getenv("TOKEN")  # من متغيرات Railway
CHANNEL_ID = os.getenv("CHANNEL_ID")  # مثال: @gsn_updates أو -100123456789
YOUTUBE_RSS = "https://www.youtube.com/feeds/videos.xml?channelid=UCxxxxx"  # ضع Channel ID الصحيح

# Flask app لإبقاء Railway نشطاً
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "البوت شغال! 🚀"

def load_last_video():
    """تحميل آخر فيديو من ملف JSON"""
    try:
        with open('last_video.json', 'r') as f:
            data = json.load(f)
            return data.get('video_id')
    except FileNotFoundError:
        logger.info("ملف last_video.json غير موجود، سيتم إنشاؤه")
        return None
    except Exception as e:
        logger.error(f"خطأ في تحميل آخر فيديو: {e}")
        return None

def save_last_video(video_id):
    """حفظ آخر فيديو في ملف JSON"""
    try:
        with open('last_video.json', 'w') as f:
            json.dump({'video_id': video_id}, f)
        logger.info(f"تم حفظ الفيديو: {video_id}")
    except Exception as e:
        logger.error(f"خطأ في حفظ الفيديو: {e}")

async def check_new_video(context: ContextTypes.DEFAULTTYPE):
    """فحص الفيديوهات الجديدة"""
    logger.info("جاري فحص قناة يوتيوب...")
    
    try:
        feed = feedparser.parse(YOUTUBE_RSS)
        
        if not feed.entries:
            logger.warning("لا توجد فيديوهات في الـ RSS")
            return
        
        latest = feed.entries[0]
        video_id = latest.get('yt_videoid', latest.get('id', '').split(':')[-1])
        
        if not video_id:
            logger.error("لم نتمكن من الحصول على معرف الفيديو")
            return
        
        last_id = load_last_video()
        logger.info(f"آخر فيديو مخزن: {last_id}")
        logger.info(f"أحدث فيديو: {video_id}")
        
        # إذا كان هذا فيديو جديد
        if video_id != last_id:
            title = latest.title
            link = latest.link
            published = latest.get('published', 'تاريخ غير متوفر')
            
            message = (
                f"🎥 **فيديو جديد على قناة غسّان مود!**\n\n"
                f"**{title}**\n\n"
                f"📅 تاريخ النشر: {published}\n\n"
                f"👈 [شاهد الفيديو هنا]({link})"
            )
            
            try:
                # إرسال إلى قناة تيليجرام
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=message,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
                logger.info(f"✅ تم إرسال فيديو جديد: {title}")
                
                # حفظ الفيديو كآخر فيديو تم إرساله
                save_last_video(video_id)
                
            except Exception as e:
                logger.error(f"❌ فشل إرسال الرسالة: {e}")
        else:
            logger.info("لا توجد فيديوهات جديدة")
            
    except Exception as e:
        logger.error(f"خطأ في فحص يوتيوب: {e}")

async def start(update: Update, context: ContextTypes.DEFAULTTYPE):
    """أمر /start"""
    await update.message.reply_text(
        "مرحباً! البوت يعمل 🚀\n"
        "سأقوم بإرسال كل فيديو جديد من قناة غسّان مود تلقائياً.\n\n"
        "الأوامر المتاحة:\n"
        "/start - عرض هذه الرسالة\n"
        "/check - فحص الفيديوهات الجديدة يدوياً"
    )

async def force_check(update: Update, context: ContextTypes.DEFAULTTYPE):
    """أمر /check لفحص يدوي"""
    await update.message.reply_text("🔍 جاري فحص قناة يوتيوب...")
    await check_new_video(context)
    await update.message.reply_text("✅ تم الانتهاء من الفحص!")

async def error_handler(update: Update, context: ContextTypes.DEFAULTTYPE):
    """معالجة الأخطاء"""
    logger.error(f"حدث خطأ: {context.error}")

def run_bot():
    """تشغيل البوت"""
    try:
        # إنشاء تطبيق البوت
        app = Application.builder().token(TOKEN).build()
        
        # إضافة المعالجات
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("check", force_check))
        
        # إضافة معالج الأخطاء
        app.add_error_handler(error_handler)
        
        # جدولة المهمة كل ساعة (3600 ثانية)
        # على Railway، نستخدم فترات أقصر لضمان العمل
        job_queue = app.job_queue
        job_queue.run_repeating(check_new_video, interval=1800, first=10)  # كل 30 دقيقة
        
        logger.info("✅ البوت بدأ العمل...")
        
        # تشغيل البوت (بدون timeout لأن Railway يعالج ذلك)
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"❌ فشل تشغيل البوت: {e}")

def run_flask():
    """تشغيل خادم Flask لإبقاء Railway نشطاً"""
    port = int(os.environ.get('PORT', 5000))
    app_flask.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # تشغيل Flask في خيط منفصل
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # تشغيل البوت
    run_bot()
