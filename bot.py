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

# ------------------- إعدادات تيليجرام -------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("لم يتم العثور على TELEGRAM_BOT_TOKEN")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN, skip_pending=True)

# ------------------- إعدادات API الجديد (الشغال) -------------------
# الـ API اللي جربته في المتصفح واشتغل
NANO_BANANA_API = "https://zecora0.serv00.net/ai/NanoBanana.php"

# ------------------- إعدادات Remini -------------------
REMINI_ENHANCE_URL = "https://reaimagine.zipoapps.com/enhance/autoenhance/"
REMINI_RESULT_URL = "https://reaimagine.zipoapps.com/enhance/request_res/"
AUTH_TOKEN = os.environ.get("REMINI_AUTH_TOKEN", "-mY6Nh3EWwV1JihHxpZEGV1hTxe2M_zDyT0i8WNeDV4buW9l02UteD6ZZrlAIO0qf6NhYA")

# تخزين إعدادات المستخدمين
user_settings = {}
temp_images = {}

# ========== دوال API الجديد ==========
def generate_image_from_text(prompt):
    """توليد صورة من نص باستخدام API الجديد"""
    try:
        url = f"{NANO_BANANA_API}?text={requests.utils.quote(prompt)}"
        logger.info(f"طلب توليد: {url}")
        response = requests.get(url, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"الرد: {data}")
            # التحقق من نجاح الطلب
            if data.get("success") == True:
                image_url = data.get("url")
                if image_url:
                    # محاولة تحميل الصورة
                    img_response = requests.get(image_url, timeout=60)
                    if img_response.status_code == 200:
                        return img_response.content
                    else:
                        # إذا فشل التحميل، نرسل الرابط
                        return image_url
            else:
                error = data.get("error", "خطأ غير معروف")
                logger.error(f"API خطأ: {error}")
            return None
        else:
            logger.error(f"HTTP خطأ: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"استثناء: {e}")
        return None

def edit_image_with_prompt(image_url, prompt):
    """تعديل صورة موجودة باستخدام API الجديد"""
    try:
        # إرسال الطلب مع رابط الصورة
        url = f"{NANO_BANANA_API}?text={requests.utils.quote(prompt)}&links={requests.utils.quote(image_url)}"
        logger.info(f"طلب تعديل: {url}")
        response = requests.get(url, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"الرد: {data}")
            if data.get("success") == True:
                image_url_result = data.get("url")
                if image_url_result:
                    img_response = requests.get(image_url_result, timeout=60)
                    if img_response.status_code == 200:
                        return img_response.content
                    else:
                        return image_url_result
            else:
                error = data.get("error", "خطأ غير معروف")
                logger.error(f"API تعديل خطأ: {error}")
            return None
        else:
            logger.error(f"HTTP تعديل خطأ: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Edit استثناء: {e}")
        return None

def upload_image_to_temp(image_bytes):
    """رفع الصورة مؤقتاً للحصول على رابط (للتعديل)"""
    try:
        # استخدام خدمة مؤقتة لرفع الصورة
        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
        response = requests.post("https://tmp.ninja/api.php?upload", files=files, timeout=30)
        if response.status_code == 200:
            return response.text.strip()
        return None
    except Exception as e:
        logger.error(f"رفع مؤقت خطأ: {e}")
        return None

# ========== دوال Remini ==========
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
        "temp_image": None,
        "temp_image_url": None
    }
    bot.send_message(message.chat.id, 
        "🌟 *بوت NanoBanana + UltraClean* 🌟\n\n"
        "• 🎨 *توليد صورة* - اكتب وصف وسأولد لك صورة\n"
        "• ✏️ *تعديل صورة* - أرسل صورة ثم اكتب التعديل\n"
        "• ✨ *تحسين الصورة* - أرسل صورة لتحسين جودتها\n\n"
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
            "temp_image": None,
            "temp_image_url": None
        }
    
    if call.data == "back_to_main":
        bot.edit_message_text(
            "🌟 *القائمة الرئيسية*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "generate_text":
        user_settings[user_id]["mode"] = "generate"
        bot.edit_message_text(
            "🎨 *توليد صورة*\n\nأرسل لي وصف الصورة.\nمثال: `قطة تجلس على سطح القمر`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "edit_image":
        user_settings[user_id]["mode"] = "edit_wait_image"
        bot.edit_message_text(
            "✏️ *تعديل صورة*\n\nأرسل لي الصورة أولاً.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_edit_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "cancel_edit":
        user_settings[user_id]["mode"] = None
        user_settings[user_id]["temp_image"] = None
        user_settings[user_id]["temp_image_url"] = None
        bot.edit_message_text(
            "❌ تم الإلغاء.\n\n🌟 *القائمة الرئيسية*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "start_enhance":
        user_settings[user_id]["mode"] = "enhance"
        bot.edit_message_text(
            "✨ *تحسين الصورة*\n\nأرسل لي الصورة.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_enhancement_type_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "open_settings":
        bot.edit_message_text(
            "⚙️ *الإعدادات:*\n\n"
            f"• نوع التحسين: {user_settings[user_id]['enhance_type']}\n"
            f"• الجودة: {user_settings[user_id]['quality']}\n"
            f"• إزالة التشويش: {'نعم' if user_settings[user_id]['denoise'] else 'لا'}\n"
            f"• زيادة الحدة: {'نعم' if user_settings[user_id]['sharpen'] else 'لا'}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_settings_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    elif call.data == "back_to_enhance":
        bot.edit_message_text(
            "✨ *تحسين الصورة*\n\nأرسل لي الصورة.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_enhancement_type_keyboard()
        )
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
            "temp_image": None,
            "temp_image_url": None
        }
    
    mode = user_settings[user_id].get("mode")
    
    if mode == "generate":
        bot.send_chat_action(message.chat.id, "upload_photo")
        bot.reply_to(message, "🎨 جاري التوليد... قد يستغرق 30-60 ثانية")
        
        result = generate_image_from_text(message.text)
        if result:
            if isinstance(result, bytes):
                bot.send_photo(message.chat.id, result, 
                    caption=f"✅ تم التوليد!\n📝 {message.text[:100]}\n\n👨‍💻 By FaresCodeX")
            else:
                bot.send_message(message.chat.id, f"✅ تم التوليد!\n📝 {message.text[:100]}\n🔗 رابط الصورة: {result}\n\n👨‍💻 By FaresCodeX")
        else:
            bot.reply_to(message, "❌ فشل التوليد. الخادم مشغول، حاول لاحقاً.")
        
        user_settings[user_id]["mode"] = None
    
    elif mode == "edit_wait_prompt":
        temp_image_url = user_settings[user_id].get("temp_image_url")
        if temp_image_url:
            bot.send_chat_action(message.chat.id, "upload_photo")
            bot.reply_to(message, "✏️ جاري التعديل... قد يستغرق 30-60 ثانية")
            
            result = edit_image_with_prompt(temp_image_url, message.text)
            if result:
                if isinstance(result, bytes):
                    bot.send_photo(message.chat.id, result,
                        caption=f"✅ تم التعديل!\n📝 {message.text[:100]}\n\n👨‍💻 By FaresCodeX")
                else:
                    bot.send_message(message.chat.id, f"✅ تم التعديل!\n📝 {message.text[:100]}\n🔗 رابط الصورة: {result}\n\n👨‍💻 By FaresCodeX")
            else:
                bot.reply_to(message, "❌ فشل التعديل. الخادم مشغول.")
        else:
            bot.reply_to(message, "❌ خطأ في الصورة، أعد المحاولة.")
        
        user_settings[user_id]["mode"] = None
        user_settings[user_id]["temp_image"] = None
        user_settings[user_id]["temp_image_url"] = None
    
    elif mode == "enhance":
        bot.reply_to(message, "📸 أرسل صورة (وليس نصاً) للتحسين.")
    
    else:
        if not message.text.startswith('/'):
            bot.reply_to(message, "🌟 استخدم الأزرار لاختيار الخدمة", reply_markup=get_main_keyboard())

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
            "temp_image": None,
            "temp_image_url": None
        }
    
    mode = user_settings[user_id].get("mode")
    
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    image_bytes = bot.download_file(file_info.file_path)
    
    if mode == "edit_wait_image":
        # رفع الصورة مؤقتاً للحصول على رابط
        temp_url = upload_image_to_temp(image_bytes)
        if temp_url:
            user_settings[user_id]["temp_image_url"] = temp_url
            user_settings[user_id]["mode"] = "edit_wait_prompt"
            bot.reply_to(message, "✅ استلمت الصورة!\n\n✏️ الآن أرسل التعديل المطلوب")
        else:
            bot.reply_to(message, "❌ فشل في رفع الصورة مؤقتاً. حاول مجدداً.")
            user_settings[user_id]["mode"] = None
    
    elif mode == "enhance":
        bot.reply_to(message, "✨ جاري التحسين... 10-20 ثانية")
        
        enhanced = enhance_image_with_remini(image_bytes)
        if enhanced:
            settings = user_settings[user_id]
            bot.send_photo(message.chat.id, enhanced,
                caption=f"✅ تم التحسين!\n🎚️ {settings['quality']}\n🎯 تشويش: {'نعم' if settings['denoise'] else 'لا'}\n\n👨‍💻 By FaresCodeX")
        else:
            bot.reply_to(message, "❌ فشل التحسين.")
        
        user_settings[user_id]["mode"] = None
    
    else:
        bot.reply_to(message, "📸 اختر الخدمة أولاً من الأزرار:\n• ✏️ تعديل صورة\n• ✨ تحسين الصورة")

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
