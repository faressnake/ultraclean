# bot.py
import requests
import telebot
from telebot import types
import time
import logging
import os
import uuid
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

# ------------------- إعدادات NanoBanana Pro -------------------
NANO_BANANA_URL = "http://de3.bot-hosting.net:21007/kilwa-nanobanana-pro"
NANO_BANANA_EDIT_URL = "http://de3.bot-hosting.net:21007/kilwa-nanobanana-edit"
NANO_BANANA_SHOW_URL = "http://de3.bot-hosting.net:21007/kilwa-show/@K_I_L_W_A10"

# ------------------- إعدادات Remini -------------------
REMINI_ENHANCE_URL = "https://reaimagine.zipoapps.com/enhance/autoenhance/"
REMINI_RESULT_URL = "https://reaimagine.zipoapps.com/enhance/request_res/"
AUTH_TOKEN = os.environ.get("REMINI_AUTH_TOKEN", "-mY6Nh3EWwV1JihHxpZEGV1hTxe2M_zDyT0i8WNeDV4buW9l02UteD6ZZrlAIO0qf6NhYA")

# تخزين إعدادات المستخدمين
user_settings = {}
temp_images = {}  # تخزين مؤقت للصور للتعديل

# ========== دوال NanoBanana ==========
def generate_image_from_text(prompt):
    """توليد صورة من نص"""
    try:
        url = f"{NANO_BANANA_URL}?text={requests.utils.quote(prompt)}"
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                image_url = data.get("image_url")
                if image_url:
                    # تحميل الصورة
                    img_response = requests.get(image_url, timeout=30)
                    if img_response.status_code == 200:
                        return img_response.content
            return None
        else:
            logger.error(f"NanoBanana خطأ: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"NanoBanana استثناء: {e}")
        return None

def edit_image_with_prompt(image_url, prompt):
    """تعديل صورة موجودة"""
    try:
        url = f"{NANO_BANANA_EDIT_URL}?text={requests.utils.quote(prompt)}&img={requests.utils.quote(image_url)}"
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                image_url_result = data.get("image_url")
                if image_url_result:
                    img_response = requests.get(image_url_result, timeout=30)
                    if img_response.status_code == 200:
                        return img_response.content
            return None
        else:
            logger.error(f"NanoBanana Edit خطأ: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"NanoBanana Edit استثناء: {e}")
        return None

def upload_image_to_temp(image_bytes):
    """رفع صورة مؤقتاً للحصول على رابط (للتعديل)"""
    # نستخدم خدمة مؤقتة لرفع الصورة
    try:
        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
        response = requests.post("https://tmp.ninja/api.php?upload", files=files, timeout=30)
        if response.status_code == 200:
            return response.text.strip()
        return None
    except:
        return None

# ========== دوال Remini (تحسين الصورة) ==========
def enhance_image_with_remini(image_bytes):
    """تحسين الصورة باستخدام Remini"""
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

# ========== لوحات المفاتيح الرئيسية ==========
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

def get_quality_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    btn_fast = types.InlineKeyboardButton("⚡ سريع", callback_data="quality_fast")
    btn_hd = types.InlineKeyboardButton("📱 HD", callback_data="quality_hd")
    btn_4k = types.InlineKeyboardButton("🌟 4K", callback_data="quality_4k")
    btn_back = types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_enhance")
    keyboard.add(btn_fast, btn_hd, btn_4k, btn_back)
    return keyboard

def get_settings_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_denoise = types.InlineKeyboardButton("🎯 إزالة التشويش ✅", callback_data="toggle_denoise")
    btn_sharpen = types.InlineKeyboardButton("📐 زيادة الحدة ✅", callback_data="toggle_sharpen")
    btn_back = types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")
    keyboard.add(btn_denoise, btn_sharpen, btn_back)
    return keyboard

def get_edit_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn_cancel = types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_edit")
    keyboard.add(btn_cancel)
    return keyboard

# ========== معالجة الأوامر والكولباك ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_settings[user_id] = {
        "enhance_type": "general",
        "quality": "hd",
        "denoise": True,
        "sharpen": True,
        "mode": None,
        "temp_image_url": None
    }
    bot.send_message(message.chat.id, 
        "🌟 *بوت NanoBanana Pro + UltraClean* 🌟\n\n"
        "• 🎨 *توليد صورة* - اكتب وصف وسأولد لك صورة\n"
        "• ✏️ *تعديل صورة* - أرسل صورة ثم اكتب التعديل المطلوب\n"
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
            "temp_image_url": None
        }
    
    # الرجوع للقائمة الرئيسية
    if call.data == "back_to_main":
        bot.edit_message_text(
            "🌟 *القائمة الرئيسية*\n\nاختر الخدمة التي تريدها:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        bot.answer_callback_query(call.id)
        return
    
    # توليد صورة من نص
    elif call.data == "generate_text":
        user_settings[user_id]["mode"] = "generate"
        bot.edit_message_text(
            "🎨 *توليد صورة*\n\nأرسل لي وصف الصورة التي تريد توليدها.\nمثال: `قطة تجلس على سطح القمر`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=None
        )
        bot.answer_callback_query(call.id)
    
    # تعديل صورة
    elif call.data == "edit_image":
        user_settings[user_id]["mode"] = "edit_wait_image"
        bot.edit_message_text(
            "✏️ *تعديل صورة*\n\nأرسل لي الصورة التي تريد تعديلها أولاً.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_edit_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    # إلغاء التعديل
    elif call.data == "cancel_edit":
        user_settings[user_id]["mode"] = None
        user_settings[user_id]["temp_image_url"] = None
        bot.edit_message_text(
            "❌ تم إلغاء العملية.\n\n🌟 *القائمة الرئيسية*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    # تحسين الصورة
    elif call.data == "start_enhance":
        user_settings[user_id]["mode"] = "enhance"
        bot.edit_message_text(
            "✨ *تحسين الصورة*\n\nأرسل لي الصورة التي تريد تحسينها.\n(يمكنك تخصيص الإعدادات من الزر أدناه)",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_enhancement_type_keyboard()
        )
        bot.answer_callback_query(call.id)
    
    # إعدادات التحسين
    elif call.data == "open_settings":
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
        bot.answer_callback_query(call.id)
    
    elif call.data == "back_to_enhance":
        bot.edit_message_text(
            "✨ *تحسين الصورة*\n\nأرسل لي الصورة التي تريد تحسينها.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=get_enhancement_type_keyboard()
        )
        bot.answer_callback_query(call.id)
    
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

# ========== معالجة الرسائل النصية والصور ==========
@bot.message_handler(func=lambda msg: True)
def handle_messages(message):
    user_id = message.from_user.id
    
    if user_id not in user_settings:
        user_settings[user_id] = {
            "enhance_type": "general",
            "quality": "hd",
            "denoise": True,
            "sharpen": True,
            "mode": None,
            "temp_image_url": None
        }
    
    mode = user_settings[user_id].get("mode")
    
    # وضع توليد صورة من نص
    if mode == "generate":
        bot.send_chat_action(message.chat.id, "typing")
        bot.reply_to(message, "🎨 جاري توليد الصورة... قد يستغرق 10-30 ثانية.")
        
        image_data = generate_image_from_text(message.text)
        if image_data:
            bot.send_photo(message.chat.id, image_data, caption=f"✅ تم توليد الصورة!\n📝 الوصف: {message.text[:100]}\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ فشل في توليد الصورة. حاول مجدداً لاحقاً.\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
        
        user_settings[user_id]["mode"] = None
    
    # وضع تعديل صورة (استلام الصورة أولاً)
    elif mode == "edit_wait_image":
        bot.reply_to(message, "📸 أرسل لي الصورة (وليس نصاً) لتعديلها.")
    
    # وضع تعديل صورة (استلام النص بعد الصورة)
    elif mode == "edit_wait_prompt":
        temp_url = user_settings[user_id].get("temp_image_url")
        if temp_url:
            bot.send_chat_action(message.chat.id, "typing")
            bot.reply_to(message, "✏️ جاري تعديل الصورة... قد يستغرق 10-30 ثانية.")
            
            image_data = edit_image_with_prompt(temp_url, message.text)
            if image_data:
                bot.send_photo(message.chat.id, image_data, caption=f"✅ تم تعديل الصورة!\n📝 التعديل: {message.text[:100]}\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ فشل في تعديل الصورة. حاول مجدداً.\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ حدث خطأ في الصورة المؤقتة. أعد المحاولة من البداية.\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
        
        user_settings[user_id]["mode"] = None
        user_settings[user_id]["temp_image_url"] = None
    
    # وضع تحسين الصورة
    elif mode == "enhance":
        bot.reply_to(message, "📸 أرسل لي صورة (وليس نصاً) لتحسينها.")
    
    # رسالة عادية خارج الأوضاع
    else:
        bot.reply_to(message, "🌟 استخدم الأزرار أدناه لاختيار الخدمة:\n\n• 🎨 توليد صورة\n• ✏️ تعديل صورة\n• ✨ تحسين الصورة", reply_markup=get_main_keyboard())

# ========== معالجة الصور ==========
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
            "temp_image_url": None
        }
    
    mode = user_settings[user_id].get("mode")
    
    # تحميل الصورة
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    image_bytes = bot.download_file(file_info.file_path)
    
    # وضع تعديل صورة (تم استلام الصورة، ننتظر النص)
    if mode == "edit_wait_image":
        # رفع الصورة مؤقتاً للحصول على رابط
        temp_url = upload_image_to_temp(image_bytes)
        if temp_url:
            user_settings[user_id]["temp_image_url"] = temp_url
            user_settings[user_id]["mode"] = "edit_wait_prompt"
            bot.reply_to(message, "✅ تم استلام الصورة!\n\n✏️ الآن أرسل لي التعديل المطلوب (مثال: `اجعلها أكثر سطوعاً` أو `حولها إلى لوحة زيتية`)", parse_mode="Markdown", reply_markup=get_edit_keyboard())
        else:
            bot.reply_to(message, "❌ فشل في رفع الصورة مؤقتاً. حاول مجدداً.")
            user_settings[user_id]["mode"] = None
    
    # وضع تحسين الصورة
    elif mode == "enhance":
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
        
        bot.reply_to(message, "✨ جاري تحسين الصورة... قد يستغرق 10-20 ثانية.")
        
        enhanced_image = enhance_image_with_remini(image_bytes)
        
        if enhanced_image:
            bot.send_photo(message.chat.id, enhanced_image, caption=f"✅ تم تحسين الصورة!\n🎚️ الجودة: {settings['quality']}\n🎯 إزالة التشويش: {'نعم' if settings['denoise'] else 'لا'}\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ فشل في تحسين الصورة. حاول مجدداً.\n\n👨‍💻 *المطور:* `By FaresCodeX`", parse_mode="Markdown")
        
        user_settings[user_id]["mode"] = None
    
    # رسالة عادية بدون وضع (طلب توليد صورة من صورة؟ غير مدعوم)
    else:
        bot.reply_to(message, "📸 استخدم الأزرار أولاً لاختيار الخدمة:\n• ✏️ تعديل صورة\n• ✨ تحسين الصورة")

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
    return "NanoBanana Pro + UltraClean Bot is running!"

if __name__ == "__main__":
    logger.info("✅ بوت NanoBanana Pro + UltraClean يعمل...")
    
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
