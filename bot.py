# bot.py
import requests
import telebot
from telebot import types
import time
import logging
import os
from io import BytesIO
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- إعدادات تيليجرام -------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("لم يتم العثور على TELEGRAM_BOT_TOKEN")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN, skip_pending=True)

# ------------------- إعدادات Remini -------------------
REMINI_ENHANCE_URL = "https://reaimagine.zipoapps.com/enhance/autoenhance/"
REMINI_RESULT_URL = "https://reaimagine.zipoapps.com/enhance/request_res/"
AUTH_TOKEN = os.environ.get("REMINI_AUTH_TOKEN", "-mY6Nh3EWwV1JihHxpZEGV1hTxe2M_zDyT0i8WNeDV4buW9l02UteD6ZZrlAIO0qf6NhYA")

# تخزين إعدادات المستخدمين
user_settings = {}

# ========== لوحات المفاتيح ==========
def get_main_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_enhance = types.InlineKeyboardButton("✨ تحسين الصورة", callback_data="start_enhance")
    btn_settings = types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="open_settings")
    keyboard.add(btn_enhance, btn_settings)
    return keyboard

def get_enhancement_type_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_general = types.InlineKeyboardButton("🔄 تحسين عام", callback_data="type_general")
    btn_face = types.InlineKeyboardButton("👤 تحسين الوجوه", callback_data="type_face")
    btn_restore = types.InlineKeyboardButton("🖼️ ترميم قديم", callback_data="type_restore")
    btn_hd = types.InlineKeyboardButton("✨ جودة عالية", callback_data="type_hd")
    keyboard.add(btn_general, btn_face, btn_restore, btn_hd)
    return keyboard

def get_quality_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    btn_fast = types.InlineKeyboardButton("⚡ سريع", callback_data="quality_fast")
    btn_hd = types.InlineKeyboardButton("📱 HD", callback_data="quality_hd")
    btn_4k = types.InlineKeyboardButton("🌟 4K", callback_data="quality_4k")
    keyboard.add(btn_fast, btn_hd, btn_4k)
    return keyboard

def get_settings_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_denoise = types.InlineKeyboardButton("🎯 إزالة التشويش ✅", callback_data="toggle_denoise")
    btn_sharpen = types.InlineKeyboardButton("📐 زيادة الحدة ✅", callback_data="toggle_sharpen")
    btn_back = types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")
    keyboard.add(btn_denoise, btn_sharpen, btn_back)
    return keyboard

# ========== معالجة الإعدادات ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_settings[user_id] = {
        "enhance_type": "general",
        "quality": "hd",
        "denoise": True,
        "sharpen": True
    }
    bot.send_message(message.chat.id, 
        "🌟 *بوت تحسين الصور - UltraClean* 🌟\n\n"
        "أرسل لي صورة وسأقوم بتحسينها وجودتها.\n"
        "يمكنك تخصيص الإعدادات من الأزرار أدناه.\n\n"
        "👨‍💻 *المطور:* `By FaresCodeX`",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "open_settings":
        bot.edit_message_text(
            "⚙️ *الإعدادات الحالية:*\n\n"
            f"• نوع التحسين: {user_settings[user_id]['enhance_type']}\n"
            f"• الجودة: {user_settings[user_id]['quality']}\n"
            f"• إزالة التشويش: {'نعم' if user_settings[user_id]['denoise'] else 'لا'}\n"
            f"• زيادة الحدة: {'نعم' if user_settings[user_id]['sharpen'] else 'لا'}\n\n"
            "👨‍💻 *المطور:* `By FaresCodeX`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_settings_keyboard()
        )
    
    elif call.data == "back_to_main":
        bot.edit_message_text(
            "🌟 *بوت تحسين الصور - UltraClean* 🌟\n\n"
            "أرسل لي صورة لتحسينها.\n\n"
            "👨‍💻 *المطور:* `By FaresCodeX`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    
    elif call.data.startswith("type_"):
        user_settings[user_id]["enhance_type"] = call.data.replace("type_", "")
        bot.answer_callback_query(call.id, f"تم اختيار: {user_settings[user_id]['enhance_type']}")
    
    elif call.data.startswith("quality_"):
        user_settings[user_id]["quality"] = call.data.replace("quality_", "")
        bot.answer_callback_query(call.id, f"تم اختيار جودة: {user_settings[user_id]['quality']}")
    
    elif call.data == "toggle_denoise":
        user_settings[user_id]["denoise"] = not user_settings[user_id]["denoise"]
        status = "✅ نعم" if user_settings[user_id]["denoise"] else "❌ لا"
        bot.answer_callback_query(call.id, f"إزالة التشويش: {status}")
    
    elif call.data == "toggle_sharpen":
        user_settings[user_id]["sharpen"] = not user_settings[user_id]["sharpen"]
        status = "✅ نعم" if user_settings[user_id]["sharpen"] else "❌ لا"
        bot.answer_callback_query(call.id, f"زيادة الحدة: {status}")
    
    elif call.data == "start_enhance":
        bot.edit_message_text(
            "📸 أرسل لي الصورة الآن.\n\n👨‍💻 *المطور:* `By FaresCodeX`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=None
        )

# ========== معالجة الصور ==========
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    
    if user_id not in user_settings:
        user_settings[user_id] = {
            "enhance_type": "general",
            "quality": "hd",
            "denoise": True,
            "sharpen": True
        }
    
    bot.reply_to(message, "📸 جاري تحسين الصورة... قد يستغرق 10-20 ثانية.\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
    
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    image_bytes = bot.download_file(file_info.file_path)
    
    settings = user_settings[user_id]
    
    if settings["quality"] == "fast":
        render_factor = 25
        denoise_strength = 0.3
    elif settings["quality"] == "hd":
        render_factor = 50
        denoise_strength = 0.6
    else:
        render_factor = 70
        denoise_strength = 0.8
    
    if not settings["denoise"]:
        denoise_strength = 0
    
    files = {
        "file": ("image.jpg", image_bytes, "image/jpeg"),
        "denoiseStrength": (None, str(denoise_strength)),
        "dest": (None, "0"),
        "first": (None, "true"),
        "renderFactor": (None, str(render_factor)),
        "style": (None, "-1")
    }
    
    headers = {"Authorization": AUTH_TOKEN}
    
    try:
        response = requests.post(REMINI_ENHANCE_URL, files=files, headers=headers, timeout=30)
        
        if response.status_code != 200:
            bot.reply_to(message, "❌ فشل في رفع الصورة.\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
            return
        
        file_name = response.headers.get("name", "")
        
        enhanced_image = None
        for attempt in range(15):
            time.sleep(2)
            result_headers = {"Authorization": AUTH_TOKEN, "name": file_name}
            result_response = requests.post(REMINI_RESULT_URL, headers=result_headers, timeout=30)
            
            if result_response.status_code == 200 and "image" in result_response.headers.get("content-type", ""):
                enhanced_image = result_response.content
                break
        
        if enhanced_image:
            bot.send_photo(message.chat.id, enhanced_image, caption="✅ تم تحسين الصورة!\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ فشل في تحسين الصورة.\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"خطأ: {e}")
        bot.reply_to(message, f"❌ حدث خطأ: {str(e)[:100]}\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")

# ------------------- خادم Flask مع Webhook -------------------
app = Flask(__name__)
WEBHOOK_PATH = f"/{TELEGRAM_TOKEN}"

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return '', 200
    abort(403)

@app.route('/')
def index():
    return "UltraClean Bot is running!"

if __name__ == "__main__":
    logger.info("✅ بوت UltraClean لتحسين الصور يعمل...")
    
    # إزالة أي webhook قديم وتعيين الجديد
    bot.remove_webhook()
    time.sleep(1)
    
    hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not hostname:
        logger.info("RENDER_EXTERNAL_HOSTNAME غير موجود. التشغيل في وضع polling...")
        bot.infinity_polling()
    else:
        webhook_url = f"https://{hostname}{WEBHOOK_PATH}"
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
        port = int(os.environ.get("PORT", 10000))
        app.run(host='0.0.0.0', port=port)