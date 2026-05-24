# bot.py
import requests
import telebot
from telebot import types
import time
import logging
import os
import base64
from io import BytesIO
from flask import Flask, request, abort

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("لم يتم العثور على TELEGRAM_BOT_TOKEN")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN, skip_pending=True)

NANO_BANANA_URL = "http://de3.bot-hosting.net:21007/kilwa-nanobanana-pro"
NANO_BANANA_EDIT_URL = "http://de3.bot-hosting.net:21007/kilwa-nanobanana-edit"

REMINI_ENHANCE_URL = "https://reaimagine.zipoapps.com/enhance/autoenhance/"
REMINI_RESULT_URL = "https://reaimagine.zipoapps.com/enhance/request_res/"
AUTH_TOKEN = os.environ.get("REMINI_AUTH_TOKEN", "-mY6Nh3EWwV1JihHxpZEGV1hTxe2M_zDyT0i8WNeDV4buW9l02UteD6ZZrlAIO0qf6NhYA")

user_settings = {}
temp_images = {}

# ========== دوال NanoBanana ==========
def generate_image_from_text(prompt):
    try:
        url = f"{NANO_BANANA_URL}?text={requests.utils.quote(prompt)}"
        response = requests.get(url, timeout=90)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                image_url = data.get("image_url")
                if image_url:
                    img_response = requests.get(image_url, timeout=60)
                    if img_response.status_code == 200:
                        return img_response.content
        return None
    except Exception as e:
        logger.error(f"توليد خطأ: {e}")
        return None

def edit_image_with_prompt(image_base64, prompt):
    """تعديل صورة - إرسال POST (الحل الصحيح)"""
    try:
        # إرسال POST بدلاً من GET لتجنب طول الرابط
        payload = {
            "text": prompt,
            "img": f"data:image/jpeg;base64,{image_base64}"
        }
        
        response = requests.post(NANO_BANANA_EDIT_URL, data=payload, timeout=90)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                image_url = data.get("image_url")
                if image_url:
                    img_response = requests.get(image_url, timeout=60)
                    if img_response.status_code == 200:
                        return img_response.content
        return None
    except Exception as e:
        logger.error(f"تعديل خطأ: {e}")
        return None

def enhance_image_with_remini(image_bytes):
    files = {
        "file": ("image.jpg", image_bytes, "image/jpeg"),
        "denoiseStrength": (None, "0.6"),
        "dest": (None, "0"),
        "first": (None, "true"),
        "renderFactor": (None, "50"),
        "style": (None, "-1")
    }
    headers = {"Authorization": AUTH_TOKEN}
    
    try:
        response = requests.post(REMINI_ENHANCE_URL, files=files, headers=headers, timeout=30)
        if response.status_code != 200:
            return None
        
        file_name = response.headers.get("name", "")
        
        for attempt in range(15):
            time.sleep(2)
            result_headers = {"Authorization": AUTH_TOKEN, "name": file_name}
            result_response = requests.post(REMINI_RESULT_URL, headers=result_headers, timeout=30)
            
            if result_response.status_code == 200 and "image" in result_response.headers.get("content-type", ""):
                return result_response.content
        return None
    except Exception as e:
        logger.error(f"Remini خطأ: {e}")
        return None

# ========== لوحات المفاتيح ==========
def get_main_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_generate = types.InlineKeyboardButton("🎨 توليد صورة", callback_data="generate_text")
    btn_edit = types.InlineKeyboardButton("✏️ تعديل صورة", callback_data="edit_image")
    btn_enhance = types.InlineKeyboardButton("✨ تحسين الصورة", callback_data="start_enhance")
    keyboard.add(btn_generate, btn_edit, btn_enhance)
    return keyboard

def get_enhancement_type_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_general = types.InlineKeyboardButton("🔄 تحسين عام", callback_data="type_general")
    btn_face = types.InlineKeyboardButton("👤 تحسين الوجوه", callback_data="type_face")
    btn_restore = types.InlineKeyboardButton("🖼️ ترميم قديم", callback_data="type_restore")
    btn_hd = types.InlineKeyboardButton("✨ جودة عالية", callback_data="type_hd")
    btn_back = types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")
    keyboard.add(btn_general, btn_face, btn_restore, btn_hd, btn_back)
    return keyboard

def get_edit_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn_cancel = types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_edit")
    keyboard.add(btn_cancel)
    return keyboard

def get_settings_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_denoise = types.InlineKeyboardButton("🎯 إزالة التشويش ✅", callback_data="toggle_denoise")
    btn_sharpen = types.InlineKeyboardButton("📐 زيادة الحدة ✅", callback_data="toggle_sharpen")
    btn_back = types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")
    keyboard.add(btn_denoise, btn_sharpen, btn_back)
    return keyboard

# ========== معالجة الأوامر ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_settings[user_id] = {
        "enhance_type": "general",
        "quality": "hd",
        "denoise": True,
        "sharpen": True,
        "mode": None,
        "temp_image": None
    }
    bot.send_message(message.chat.id, 
        "🌟 *بوت NanoBanana Pro + UltraClean* 🌟\n\n"
        "• 🎨 *توليد صورة* - اكتب وصف\n"
        "• ✏️ *تعديل صورة* - أرسل صورة ثم اكتب التعديل\n"
        "• ✨ *تحسين الصورة* - أرسل صورة\n\n"
        "👨‍💻 *المطور:* `By FaresCodeX`",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if user_id not in user_settings:
        user_settings[user_id] = {
            "enhance_type": "general",
            "quality": "hd",
            "denoise": True,
            "sharpen": True,
            "mode": None,
            "temp_image": None
        }
    
    if call.data == "back_to_main":
        bot.edit_message_text("🌟 *القائمة الرئيسية*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_keyboard())
        bot.answer_callback_query(call.id)
    
    elif call.data == "generate_text":
        user_settings[user_id]["mode"] = "generate"
        bot.edit_message_text("🎨 *توليد صورة*\n\nأرسل لي وصف الصورة.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
    
    elif call.data == "edit_image":
        user_settings[user_id]["mode"] = "edit_wait_image"
        bot.edit_message_text("✏️ *تعديل صورة*\n\nأرسل لي الصورة أولاً.", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_edit_keyboard())
        bot.answer_callback_query(call.id)
    
    elif call.data == "cancel_edit":
        user_settings[user_id]["mode"] = None
        user_settings[user_id]["temp_image"] = None
        bot.edit_message_text("❌ تم الإلغاء.\n\n🌟 *القائمة الرئيسية*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_keyboard())
        bot.answer_callback_query(call.id)
    
    elif call.data == "start_enhance":
        user_settings[user_id]["mode"] = "enhance"
        bot.edit_message_text("✨ *تحسين الصورة*\n\nأرسل لي الصورة.", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_enhancement_type_keyboard())
        bot.answer_callback_query(call.id)
    
    elif call.data == "open_settings":
        bot.edit_message_text(
            f"⚙️ *الإعدادات:*\n\n• نوع التحسين: {user_settings[user_id]['enhance_type']}\n• الجودة: {user_settings[user_id]['quality']}\n• إزالة التشويش: {'نعم' if user_settings[user_id]['denoise'] else 'لا'}\n• زيادة الحدة: {'نعم' if user_settings[user_id]['sharpen'] else 'لا'}",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_settings_keyboard())
        bot.answer_callback_query(call.id)
    
    elif call.data == "back_to_enhance":
        bot.edit_message_text("✨ *تحسين الصورة*\n\nأرسل لي الصورة.", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_enhancement_type_keyboard())
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("type_"):
        user_settings[user_id]["enhance_type"] = call.data.replace("type_", "")
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("quality_"):
        user_settings[user_id]["quality"] = call.data.replace("quality_", "")
        bot.answer_callback_query(call.id)
    
    elif call.data == "toggle_denoise":
        user_settings[user_id]["denoise"] = not user_settings[user_id]["denoise"]
        bot.answer_callback_query(call.id)
    
    elif call.data == "toggle_sharpen":
        user_settings[user_id]["sharpen"] = not user_settings[user_id]["sharpen"]
        bot.answer_callback_query(call.id)

# ========== معالجة الرسائل ==========
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    
    if user_id not in user_settings:
        user_settings[user_id] = {
            "enhance_type": "general",
            "quality": "hd",
            "denoise": True,
            "sharpen": True,
            "mode": None,
            "temp_image": None
        }
    
    mode = user_settings[user_id].get("mode")
    
    if mode == "generate":
        bot.reply_to(message, "🎨 جاري التوليد...")
        image_data = generate_image_from_text(message.text)
        if image_data:
            bot.send_photo(message.chat.id, image_data, caption=f"✅ تم التوليد!\n📝 {message.text[:100]}\n\n👨‍💻 By FaresCodeX")
        else:
            bot.reply_to(message, "❌ فشل التوليد. حاول لاحقاً.")
        user_settings[user_id]["mode"] = None
    
    elif mode == "edit_wait_prompt":
        temp_image = user_settings[user_id].get("temp_image")
        if temp_image:
            bot.reply_to(message, "✏️ جاري التعديل...")
            image_data = edit_image_with_prompt(temp_image, message.text)
            if image_data:
                bot.send_photo(message.chat.id, image_data, caption=f"✅ تم التعديل!\n📝 {message.text[:100]}\n\n👨‍💻 By FaresCodeX")
            else:
                bot.reply_to(message, "❌ فشل التعديل. الخادم مشغول.")
        else:
            bot.reply_to(message, "❌ خطأ في الصورة.")
        user_settings[user_id]["mode"] = None
        user_settings[user_id]["temp_image"] = None
    
    else:
        if not message.text.startswith('/'):
            bot.reply_to(message, "🌟 استخدم الأزرار", reply_markup=get_main_keyboard())

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    
    if user_id not in user_settings:
        user_settings[user_id] = {
            "enhance_type": "general",
            "quality": "hd",
            "denoise": True,
            "sharpen": True,
            "mode": None,
            "temp_image": None
        }
    
    mode = user_settings[user_id].get("mode")
    
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    image_bytes = bot.download_file(file_info.file_path)
    
    if mode == "edit_wait_image":
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        user_settings[user_id]["temp_image"] = image_base64
        user_settings[user_id]["mode"] = "edit_wait_prompt"
        bot.reply_to(message, "✅ استلمت الصورة!\n\n✏️ الآن أرسل التعديل المطلوب")
    
    elif mode == "enhance":
        bot.reply_to(message, "✨ جاري التحسين...")
        enhanced = enhance_image_with_remini(image_bytes)
        if enhanced:
            bot.send_photo(message.chat.id, enhanced, caption=f"✅ تم التحسين!\n\n👨‍💻 By FaresCodeX")
        else:
            bot.reply_to(message, "❌ فشل التحسين.")
        user_settings[user_id]["mode"] = None
    
    else:
        bot.reply_to(message, "📸 اختر الخدمة أولاً:\n• ✏️ تعديل صورة\n• ✨ تحسين الصورة")

# ------------------- خادم Flask -------------------
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
    return "Bot is running!"

if __name__ == "__main__":
    logger.info("✅ البوت يعمل...")
    bot.remove_webhook()
    time.sleep(1)
    
    hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not hostname:
        bot.infinity_polling()
    else:
        webhook_url = f"https://{hostname}{WEBHOOK_PATH}"
        bot.set_webhook(url=webhook_url)
        port = int(os.environ.get("PORT", 10000))
        app.run(host='0.0.0.0', port=port)
