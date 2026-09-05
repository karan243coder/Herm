import os
import sys
import io
import re
import base64
import zipfile
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from providers.router import ModelProviderRouter
from agent.loop import execute_agentic_turn
from memory.store import clear_history, reset_all, set_custom_identity, fetch_history
from cron.scheduler import start_cron_worker, add_cron_job, list_cron_jobs
from tools.registry import (
    exec_generate_image, exec_qr, exec_tts, exec_crypto, exec_weather, exec_pip_install
)

# ----------------- LOGGING CONFIGURATION ----------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ----------------- KOYEB HEALTH CHECK SERVER (Port 8080) ----------------- #
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Nous Hermes Ultra Agent is Live")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health server active on 0.0.0.0:{port}")
        server.serve_forever()
    except Exception as e:
        logger.warning(f"Health server error: {e}")

threading.Thread(target=start_health_server, daemon=True).start()

# ----------------- ENVIRONMENT VARIABLES ----------------- #
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not TELEGRAM_BOT_TOKEN or not OPENROUTER_API_KEY:
    logger.critical("FATAL: TELEGRAM_BOT_TOKEN and OPENROUTER_API_KEY must be set!")
    sys.exit(1)

# Telegram Client & Model Provider
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None)
model_router = ModelProviderRouter(OPENROUTER_API_KEY)

# Start Background Cron Scheduler
start_cron_worker(bot)


# ----------------- INLINE KEYBOARD ----------------- #
def get_action_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    btn_voice = InlineKeyboardButton("🔊 Bol Kar Sunao", callback_data="tts_last")
    btn_clear = InlineKeyboardButton("🧹 Clear Memory", callback_data="clear_mem")
    markup.row(btn_voice, btn_clear)
    return markup


# ----------------- MESSAGE SENDER & DISPATCHER ----------------- #
def send_agent_response(chat_id: int, text: str, artifacts: dict, reply_to_id: int | None = None, send_audio: bool = False):
    # 1. Send text with action keyboard
    if text:
        markup = get_action_keyboard()
        if len(text) <= 4000:
            try:
                bot.send_message(chat_id, text, reply_to_message_id=reply_to_id, reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, text, reply_markup=markup)
        else:
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for idx, ch in enumerate(chunks):
                if idx == len(chunks) - 1:
                    bot.send_message(chat_id, ch, reply_markup=markup)
                else:
                    bot.send_message(chat_id, ch)

    # 2. Voice Note
    if send_audio and text:
        bot.send_chat_action(chat_id, 'record_audio')
        abio = exec_tts(text)
        if abio:
            bot.send_voice(chat_id, abio, caption="🎙️ *Spoken Voice Note*", parse_mode="Markdown")

    # 3. Images
    for img_p in artifacts.get("images", []):
        bot.send_chat_action(chat_id, 'upload_photo')
        ibio = exec_generate_image(img_p)
        if ibio:
            bot.send_photo(chat_id, ibio, caption=f"🎨 *Generated:* `{img_p[:90]}`", parse_mode="Markdown")

    # 4. QR Codes
    for qr_d in artifacts.get("qrs", []):
        bot.send_chat_action(chat_id, 'upload_photo')
        qbio = exec_qr(qr_d)
        if qbio:
            bot.send_photo(chat_id, qbio, caption=f"📱 *QR Code:* `{qr_d[:90]}`", parse_mode="Markdown")

    # 5. Files
    for fo in artifacts.get("files", []):
        fn = fo.get("filename", "code.py")
        fc = fo.get("content", "")
        fbio = io.BytesIO(fc.encode('utf-8'))
        fbio.name = fn
        bot.send_document(chat_id, fbio, caption=f"📁 *Generated File:* `{fn}`", parse_mode="Markdown")

    # 6. Project ZIPs
    for zo in artifacts.get("zips", []):
        zname = zo.get("zip_name", "project.zip")
        zfiles = zo.get("files", {})
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, fcontent in zfiles.items():
                zf.writestr(fname, fcontent)
        zip_buffer.seek(0)
        zip_buffer.name = zname
        bot.send_document(chat_id, zip_buffer, caption=f"📦 *Project Bundle:* `{zname}` ({len(zfiles)} files)", parse_mode="Markdown")


# ----------------- CALLBACK QUERY HANDLER ----------------- #
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    if call.data == "tts_last":
        bot.answer_callback_query(call.id, "Voice generate ho rahi hai...")
        bot.send_chat_action(chat_id, 'record_audio')
        history = fetch_history(chat_id, limit=2)
        last_text = ""
        for h in reversed(history):
            if h["role"] == "assistant":
                last_text = h["content"]
                break
        if last_text:
            abio = exec_tts(last_text)
            if abio:
                bot.send_voice(chat_id, abio, caption="🎙️ *Spoken Audio Note*", parse_mode="Markdown")
    elif call.data == "clear_mem":
        clear_history(chat_id)
        bot.answer_callback_query(call.id, "Memory cleared!")
        bot.send_message(chat_id, "🧹 Conversation history cleared.")


# ----------------- TELEGRAM COMMAND HANDLERS ----------------- #
@bot.message_handler(commands=['start'])
def cmd_start(message):
    welcome = (
        "🚀 *Nous Hermes Ultra Autonomous Agent (Lexi Lore)* 🚀\n\n"
        "Main official *NousResearch/hermes-agent* architecture par chal raha hoon!\n\n"
        "✨ *Core Superpowers:*\n"
        "• 📦 **Live Pip Package Installer:** `/install <package>` se runtime me koi bhi library install karein bina redeploy kiye!\n"
        "• 🌐 **Live Web Search & Scraper:** Internet se taaza information nikalna.\n"
        "• 💻 **Terminal Python Sandbox:** Code likh kar live run karna (FFmpeg & OpenCV enabled).\n"
        "• 🎨 **Flux HD Image:** _'Sunny Leone ki photo bhej'_ ya _'Cyberpunk car banao'_\n"
        "• 🎙️ **Voice Notes:** Message ke niche _'Bol Kar Sunao'_ button dabao ya bolo _'Voice note bhejo'_.\n"
        "• 📊 **Live Crypto & Weather:** Bitcoin, Solana rates aur mausam info.\n"
        "• 📱 **QR Generator:** Instant QR code banana.\n"
        "• 📦 **ZIP Project Exporter:** Full multi-file project zip bana kar dena.\n"
        "• ⏰ **Cron Reminders:** _'10 minute baad mujhe remind karna'_.\n"
        "• 👁️ **Vision:** Mujhe koi bhi photo bhej kar sawal pucho!\n\n"
        "Direct natural Hindi/Hinglish/English me baat karein!"
    )
    bot.reply_to(message, welcome, parse_mode="Markdown")


@bot.message_handler(commands=['install', 'pip'])
def cmd_install_pkg(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "ℹ️ *Usage:* `/install <package_name>`\nExample: `/install beautifulsoup4` ya `/install sympy`", parse_mode="Markdown")
        return
    pkg_name = args[1].strip()
    bot.send_chat_action(message.chat.id, 'typing')
    status_msg = bot.reply_to(message, f"⏳ *Installing `{pkg_name}` at runtime via pip...*", parse_mode="Markdown")
    res = exec_pip_install(pkg_name)
    bot.edit_message_text(res, message.chat.id, status_msg.message_id)


@bot.message_handler(commands=['voice', 'audio', 'speak'])
def cmd_voice(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "ℹ️ *Usage:* `/voice <kya bolna hai>`", parse_mode="Markdown")
        return
    text = args[1].strip()
    bot.send_chat_action(message.chat.id, 'record_audio')
    abio = exec_tts(text)
    if abio:
        bot.send_voice(message.chat.id, abio, caption=f"🎙️ `{text[:80]}`", parse_mode="Markdown")


@bot.message_handler(commands=['qr'])
def cmd_qr(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "ℹ️ *Usage:* `/qr <link ya text>`", parse_mode="Markdown")
        return
    qbio = exec_qr(args[1].strip())
    if qbio:
        bot.send_photo(message.chat.id, qbio, caption=f"📱 *QR Code:* `{args[1].strip()}`", parse_mode="Markdown")


@bot.message_handler(commands=['remind', 'cron'])
def cmd_remind(message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        bot.reply_to(message, "ℹ️ *Usage:* `/remind <minutes> <task>`\nExample: `/remind 10 Check server`", parse_mode="Markdown")
        return
    try:
        mins = int(args[1])
        task_text = args[2]
        res = add_cron_job(message.chat.id, task_text, mins * 60)
        bot.reply_to(message, f"⏰ {res}")
    except ValueError:
        bot.reply_to(message, "❌ Minutes number me hone chahiye.")


@bot.message_handler(commands=['reminders'])
def cmd_list_reminders(message):
    res = list_cron_jobs(message.chat.id)
    bot.reply_to(message, res)


@bot.message_handler(commands=['clear'])
def cmd_clear(message):
    clear_history(message.chat.id)
    bot.reply_to(message, "🧹 Conversation history cleared!")


@bot.message_handler(commands=['reset'])
def cmd_reset(message):
    reset_all(message.chat.id)
    bot.reply_to(message, "🔄 Bot reset to pure Blank Slate Hermes Agent.")


# ----------------- PHOTO / VISION HANDLER ----------------- #
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    caption = message.caption or "Analyze this image and explain what is inside."
    bot.send_chat_action(chat_id, 'typing')
    try:
        finfo = bot.get_file(message.photo[-1].file_id)
        dfile = bot.download_file(finfo.file_path)
        b64 = base64.b64encode(dfile).decode('utf-8')
        
        resp = model_router.client.chat.completions.create(
            model="openrouter/free",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": caption},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }
            ],
            max_tokens=1500
        )
        reply = resp.choices[0].message.content.strip()
        bot.reply_to(message, reply, reply_markup=get_action_keyboard())
    except Exception as e:
        logger.error(f"Vision error: {e}")
        bot.reply_to(message, "❌ Photo analyze karne me dikkat aayi.")


# ----------------- DOCUMENT INGESTION ----------------- #
@bot.message_handler(content_types=['document'])
def handle_doc(message):
    chat_id = message.chat.id
    try:
        finfo = bot.get_file(message.document.file_id)
        if message.document.file_size < 1000000:
            dfile = bot.download_file(finfo.file_path)
            content = dfile.decode('utf-8', errors='ignore')
            prompt = f"User uploaded document '{message.document.file_name}':\n```\n{content[:3000]}\n```\nPlease analyze and explain it."
            bot.send_chat_action(chat_id, 'typing')
            rep, art = execute_agentic_turn(chat_id, prompt, model_router)
            send_agent_response(chat_id, rep, art, message.message_id)
            return
        bot.reply_to(message, "📁 File received.")
    except Exception as e:
        logger.error(f"Doc error: {e}")
        bot.reply_to(message, "❌ File read karne me dikkat aayi.")


# ----------------- NATURAL LANGUAGE ROUTER ----------------- #
IMAGE_KEYWORDS = ["photo", "image", "pic", "picture", "wallpaper", "portrait", "dp"]
ACTION_KEYWORDS = ["bhej", "vej", "banao", "dikhao", "generate", "send", "draw", "render", "create", "nikal", "do", "de"]

def detect_natural_image(text: str) -> str | None:
    t = text.strip().lower()
    if any(k in t for k in IMAGE_KEYWORDS) and any(a in t for a in ACTION_KEYWORDS):
        cleaned = re.sub(r'\b(photo|image|picture|pic|wallpaper|portrait|bhej|vej|banao|dikhao|generate|send|draw|create|karo|kar|do|de|toh|na|mujhe|tum|uska|unki|unka|ek|ki|ka|ke|please|bhai)\b', ' ', t, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return f"{cleaned} portrait photograph, 8k resolution, cinematic lighting, photorealistic" if len(cleaned) >= 2 else "beautiful cinematic 8k portrait"
    return None

def detect_qr_request(text: str) -> str | None:
    t = text.strip().lower()
    if "qr" in t and ("banao" in t or "generate" in t or "create" in t or "code" in t):
        cleaned = re.sub(r'\b(qr|code|banao|generate|karo|create|ka|ki|ke|for|link|please|bhai)\b', ' ', t, flags=re.IGNORECASE).strip()
        return cleaned if len(cleaned) > 2 else "https://telegram.org"
    return None

def detect_crypto_request(text: str) -> str | None:
    t = text.strip().lower()
    crypto_coins = ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "doge", "dogecoin", "shiba", "xrp", "cardano"]
    for coin in crypto_coins:
        if coin in t and ("price" in t or "rate" in t or "kitna" in t or "bhav" in t or "value" in t):
            name_map = {"btc": "bitcoin", "eth": "ethereum", "sol": "solana", "doge": "dogecoin", "shib": "shiba-inu"}
            return name_map.get(coin, coin)
    return None

def detect_weather_request(text: str) -> str | None:
    t = text.strip().lower()
    if "weather" in t or "mausam" in t or "temperature" in t:
        cleaned = re.sub(r'\b(weather|mausam|temperature|kya|hai|batao|ka|ki|ke|in|city|today|aaj)\b', ' ', t, flags=re.IGNORECASE).strip()
        return cleaned if len(cleaned) >= 2 else "Patna"
    return None

def detect_pip_request(text: str) -> str | None:
    t = text.strip().lower()
    m = re.match(r'^(?:pip\s+install|install\s+package|package\s+install\s+karo|install\s+karo)\s+([a-zA-Z0-9_\-<=>.]+)', t)
    if m:
        return m.group(1).strip()
    return None

def detect_voice_request(text: str) -> bool:
    t = text.strip().lower()
    return any(p in t for p in ["bol kar", "bolke", "voice note", "audio me", "audio sunao", "sunao"])


@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_natural_chat(message):
    chat_id = message.chat.id
    user_text = message.text.strip()
    if not user_text:
        return

    # 1. Natural Pip Install Detection (e.g. "pip install pandas")
    pip_pkg = detect_pip_request(user_text)
    if pip_pkg:
        bot.send_chat_action(chat_id, 'typing')
        st = bot.reply_to(message, f"⏳ *Installing `{pip_pkg}` live at runtime...*", parse_mode="Markdown")
        res = exec_pip_install(pip_pkg)
        bot.edit_message_text(res, chat_id, st.message_id)
        return

    # 2. Natural Image Generation
    img_p = detect_natural_image(user_text)
    if img_p:
        bot.send_chat_action(chat_id, 'upload_photo')
        ibio = exec_generate_image(img_p)
        if ibio:
            bot.send_photo(chat_id, ibio, caption=f"🎨 *Generated:* `{img_p[:90]}`", parse_mode="Markdown")
            return

    # 3. Natural QR Code Request
    qr_data = detect_qr_request(user_text)
    if qr_data:
        bot.send_chat_action(chat_id, 'upload_photo')
        qbio = exec_qr(qr_data)
        if qbio:
            bot.send_photo(chat_id, qbio, caption=f"📱 *QR Code:* `{qr_data}`", parse_mode="Markdown")
            return

    # 4. Natural Crypto Price
    crypto_coin = detect_crypto_request(user_text)
    if crypto_coin:
        c_res = exec_crypto(crypto_coin)
        bot.reply_to(message, c_res)
        return

    # 5. Natural Weather
    city_name = detect_weather_request(user_text)
    if city_name and len(user_text.split()) < 7:
        w_res = exec_weather(city_name)
        bot.reply_to(message, w_res)
        return

    # 6. Check voice note intent
    wants_voice = detect_voice_request(user_text)

    # 7. Natural Clear/Reset
    if any(p in user_text.lower() for p in ["pichli baatein bhul jao", "memory clear karo", "chat clear karo"]):
        clear_history(chat_id)
        bot.reply_to(message, "🧹 Pichli baatein bhul gaya hoon!")
        return

    # 8. Agentic Multi-Step Turn
    bot.send_chat_action(chat_id, 'typing')
    reply, artifacts = execute_agentic_turn(chat_id, user_text, model_router)
    send_agent_response(chat_id, reply, artifacts, message.message_id, send_audio=wants_voice)


# ----------------- MAIN STARTUP ----------------- #
if __name__ == "__main__":
    logger.info("Starting Official Nous Hermes Autonomous Agent Framework...")
    print("🚀 Nous Hermes Agent is ONLINE! Ready across all modalities.")
    bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)
