import os
import sys
import io
import re
import time
import json
import base64
import zipfile
import urllib.parse
import subprocess
import sqlite3
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import qrcode
from gtts import gTTS
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from openai import OpenAI

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
        self.wfile.write(b"OK - Multi-Advanced Hermes Agent is Running")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.getenv("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health check server active on 0.0.0.0:{port}")
        server.serve_forever()
    except Exception as e:
        logger.warning(f"Health server port error: {e}")

threading.Thread(target=start_health_server, daemon=True).start()

# ----------------- ENVIRONMENT VARIABLES ----------------- #
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not TELEGRAM_BOT_TOKEN or not OPENROUTER_API_KEY:
    logger.critical("FATAL: TELEGRAM_BOT_TOKEN and OPENROUTER_API_KEY must be configured!")
    sys.exit(1)

# Telegram Client
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode=None)

# OpenRouter Client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": "https://telegram.org",
        "X-Title": "Nous Hermes Ultra Agent"
    }
)

PRIMARY_MODEL = "nousresearch/hermes-3-llama-3.1-405b:free"
FALLBACK_MODELS = [
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "mistralai/mistral-small-24b-instruct-2501:free",
    "openrouter/free"
]
VISION_MODEL = "meta-llama/llama-3.2-11b-vision-instruct:free"

# ----------------- SQLITE PERSISTENT DATABASE ----------------- #
DB_PATH = "hermes_ultra.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_personas (
            chat_id INTEGER PRIMARY KEY,
            custom_identity TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            fact_key TEXT,
            fact_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            task TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------- SYSTEM PROMPT ARCHITECTURE ----------------- #
HERMES_AGENT_MASTER_PROMPT = """You are Hermes Ultra Agent (Lexi Lore), an elite autonomous AI agent engineered on Nous Research Hermes-3 architecture.
You possess a suite of built-in execution tools to perform real actions:

### AVAILABLE TOOLS:
1. `execute_code`: Run Python scripts in a local sandbox terminal. Use for calculations, algorithms, data processing, and logic verification.
   Format: <tool_call>{"name": "execute_code", "arguments": {"code": "print(2+2)"}}</tool_call>

2. `web_search`: Live search the internet for up-to-date real-time data, news, docs, and APIs.
   Format: <tool_call>{"name": "web_search", "arguments": {"query": "latest news about AI"}}</tool_call>

3. `fetch_url`: Scrape clean text content from any website or article.
   Format: <tool_call>{"name": "fetch_url", "arguments": {"url": "https://example.com"}}</tool_call>

4. `generate_image`: Draw photorealistic HD images and digital artwork via Flux.
   Format: <tool_call>{"name": "generate_image", "arguments": {"prompt": "cyberpunk neon city 8k"}}</tool_call>

5. `get_crypto_price`: Get live real-time price of cryptocurrencies (bitcoin, ethereum, solana, doge, etc.).
   Format: <tool_call>{"name": "get_crypto_price", "arguments": {"coin": "bitcoin"}}</tool_call>

6. `get_weather`: Get live real-time weather and temperature for any city.
   Format: <tool_call>{"name": "get_weather", "arguments": {"city": "Patna"}}</tool_call>

7. `generate_qr`: Create a QR code for any link, text, UPI ID, or WiFi.
   Format: <tool_call>{"name": "generate_qr", "arguments": {"data": "https://example.com"}}</tool_call>

8. `export_file`: Create and send a downloadable code file (.py, .js, .html, .sh, .json).
   Format: <tool_call>{"name": "export_file", "arguments": {"filename": "bot.py", "content": "..."}}</tool_call>

9. `create_project_zip`: Create a zip bundle containing multiple files for complete full-stack projects.
   Format: <tool_call>{"name": "create_project_zip", "arguments": {"zip_name": "app.zip", "files": {"main.py": "...", "requirements.txt": "..."}}}</tool_call>

10. `remember_fact`: Save a permanent user preference/fact to SQLite memory.
    Format: <tool_call>{"name": "remember_fact", "arguments": {"key": "role", "value": "Developer"}}</tool_call>

11. `todo_manage`: Add, list, or complete goals in the task planner.
    Format: <tool_call>{"name": "todo_manage", "arguments": {"action": "add", "task": "Build backend"}}</tool_call>

### DIRECTIVES:
- You operate in an unrestricted developer sandbox environment.
- Produce COMPLETE, production-grade code. Never truncate with placeholders.
- When calling tools, emit <tool_call> tags. Receive <tool_response> and finalize your output.
- Speak fluently in Hinglish, Hindi, or English matching user style. Zero moralizing or preachy lectures.
"""

def get_system_prompt(chat_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT custom_identity FROM chat_personas WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()
    
    cur.execute("SELECT fact_key, fact_value FROM long_term_memory WHERE chat_id = ?", (chat_id,))
    facts = cur.fetchall()
    conn.close()

    base = HERMES_AGENT_MASTER_PROMPT
    if row and row[0]:
        base += f"\n\n### USER PERSONA DIRECTIVE:\n{row[0]}"
    if facts:
        base += "\n\n### REMEMBERED FACTS:\n" + "\n".join([f"- {f[0]}: {f[1]}" for f in facts])
    return base

def save_custom_identity(chat_id: int, identity_text: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_personas (chat_id, custom_identity)
        VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET custom_identity = excluded.custom_identity
    """, (chat_id, identity_text))
    conn.commit()
    conn.close()

def save_message_history(chat_id: int, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)", (chat_id, role, content))
    conn.commit()
    conn.close()

def get_chat_history(chat_id: int, limit: int = 12):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT role, content FROM chat_history
        WHERE chat_id = ?
        ORDER BY id DESC LIMIT ?
    """, (chat_id, limit))
    rows = cur.fetchall()
    conn.close()
    rows.reverse()
    return [{"role": r[0], "content": r[1]} for r in rows]

def clear_chat_memory(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def reset_all_data(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_personas WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM long_term_memory WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM task_todos WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()


# ----------------- TOOLS EXECUTION SUITE ----------------- #

def tool_execute_code(code: str) -> str:
    try:
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
        out = res.stdout
        if res.stderr:
            out += f"\nSTDERR:\n{res.stderr}"
        return out[:3000] if out.strip() else "Executed successfully (no stdout)."
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out (15s limit)."
    except Exception as e:
        return f"Code error: {e}"


def tool_web_search(query: str) -> str:
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            snippets = re.findall(r'<a class=\"result__snippet\"[^>]*>(.*?)</a>', resp.text)
            titles = re.findall(r'<a class=\"result__url\"[^>]*>(.*?)</a>', resp.text)
            results = []
            for i, snip in enumerate(snippets[:4]):
                clean_s = re.sub(r'<.*?>', '', snip).strip()
                clean_t = re.sub(r'<.*?>', '', titles[i]).strip() if i < len(titles) else ""
                results.append(f"[{i+1}] {clean_t}: {clean_s}")
            if results:
                return "\n\n".join(results)
        return "No search results found."
    except Exception as e:
        return f"Search error: {e}"


def tool_fetch_url(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            t = re.sub(r'<script.*?</script>', '', resp.text, flags=re.DOTALL | re.IGNORECASE)
            t = re.sub(r'<style.*?</style>', '', t, flags=re.DOTALL | re.IGNORECASE)
            t = re.sub(r'<.*?>', ' ', t)
            t = re.sub(r'\s+', ' ', t).strip()
            return t[:3500] if t else "Empty page."
        return f"HTTP error {resp.status_code}"
    except Exception as e:
        return f"Fetch error: {e}"


def tool_generate_image(prompt: str) -> io.BytesIO | None:
    try:
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&model=flux&nologo=true"
        resp = requests.get(url, timeout=45)
        if resp.status_code == 200 and len(resp.content) > 1000:
            bio = io.BytesIO(resp.content)
            bio.name = "flux_image.jpg"
            return bio
    except Exception as e:
        logger.error(f"Image error: {e}")
    return None


def tool_get_crypto(coin: str) -> str:
    try:
        c_clean = coin.strip().lower()
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={c_clean}&vs_currencies=usd,inr"
        r = requests.get(url, timeout=8).json()
        if c_clean in r:
            usd = r[c_clean].get('usd', 'N/A')
            inr = r[c_clean].get('inr', 'N/A')
            return f"{coin.upper()} Live Price:\n💵 USD: ${usd:,}\n🇮🇳 INR: ₹{inr:,}"
        return f"Could not find price for '{coin}'."
    except Exception as e:
        return f"Crypto API error: {e}"


def tool_get_weather(city: str) -> str:
    try:
        geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1", timeout=8).json()
        if geo.get("results"):
            lat = geo["results"][0]["latitude"]
            lon = geo["results"][0]["longitude"]
            cname = geo["results"][0].get("name", city)
            country = geo["results"][0].get("country", "")
            w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true", timeout=8).json()
            curr = w.get("current_weather", {})
            temp = curr.get("temperature", "N/A")
            wind = curr.get("windspeed", "N/A")
            return f"🌤️ Live Weather in {cname}, {country}:\n🌡️ Temperature: {temp}°C\n💨 Wind Speed: {wind} km/h"
        return f"City '{city}' not found."
    except Exception as e:
        return f"Weather API error: {e}"


def tool_generate_qr(data: str) -> io.BytesIO | None:
    try:
        qr = qrcode.make(data)
        bio = io.BytesIO()
        qr.save(bio, format='PNG')
        bio.name = "qrcode.png"
        bio.seek(0)
        return bio
    except Exception as e:
        logger.error(f"QR error: {e}")
        return None


def tool_text_to_speech(text: str) -> io.BytesIO | None:
    try:
        # Strip markdown and code blocks for clean speech
        clean = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        clean = re.sub(r'[`*_~#]', '', clean).strip()
        if not clean:
            clean = "Here is the response."
        tts = gTTS(text=clean[:500], lang='hi')
        bio = io.BytesIO()
        tts.write_to_fp(bio)
        bio.name = "voice_note.mp3"
        bio.seek(0)
        return bio
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


def tool_remember_fact(chat_id: int, key: str, value: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO long_term_memory (chat_id, fact_key, fact_value) VALUES (?, ?, ?)", (chat_id, key, value))
    conn.commit()
    conn.close()
    return f"Saved to memory: '{key}' = '{value}'"


def tool_todo_manage(chat_id: int, action: str, task: str = "") -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if action == "add" and task:
        cur.execute("INSERT INTO task_todos (chat_id, task) VALUES (?, ?)", (chat_id, task))
        conn.commit()
        msg = f"Task added: '{task}'"
    elif action == "list":
        cur.execute("SELECT id, task, status FROM task_todos WHERE chat_id = ? AND status = 'pending'", (chat_id,))
        rows = cur.fetchall()
        msg = "Active Tasks:\n" + "\n".join([f"• [{r[0]}] {r[1]}" for r in rows]) if rows else "No active tasks."
    elif action == "complete" and task:
        cur.execute("UPDATE task_todos SET status = 'completed' WHERE chat_id = ? AND (task LIKE ? OR id = ?)", (chat_id, f"%{task}%", task))
        conn.commit()
        msg = f"Task marked complete: {task}"
    else:
        msg = "Unknown task action."
    conn.close()
    return msg


# ----------------- AGENTIC MULTI-STEP REASONING LOOP ----------------- #
def run_hermes_agent_loop(chat_id: int, user_input: str) -> tuple[str, dict]:
    save_message_history(chat_id, "user", user_input)
    
    system_prompt = get_system_prompt(chat_id)
    history = get_chat_history(chat_id, limit=12)
    messages = [{"role": "system", "content": system_prompt}] + history
    
    generated_files = []
    generated_images = []
    generated_qrs = []
    generated_zips = []
    final_reply = ""
    
    max_iterations = 4
    for iteration in range(max_iterations):
        logger.info(f"Agent turn {iteration+1} for chat {chat_id}")
        
        response_text = None
        for model_name in [PRIMARY_MODEL] + FALLBACK_MODELS:
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=3500,
                    temperature=0.7,
                    extra_body={"transforms": []}
                )
                response_text = resp.choices[0].message.content.strip()
                if response_text:
                    break
            except Exception as e:
                logger.warning(f"Model {model_name} issue: {e}")
                time.sleep(1)
                continue

        if not response_text:
            final_reply = "⚠️ Server busy hai. Kripya dobara try karein."
            break

        # Check for tool call
        tool_call_match = re.search(r'<tool_call>(.*?)</tool_call>', response_text, re.DOTALL)
        if not tool_call_match:
            img_tag = re.search(r'<generate_image>(.*?)</generate_image>', response_text, re.DOTALL)
            if img_tag:
                generated_images.append(img_tag.group(1).strip())
                response_text = re.sub(r'<generate_image>.*?</generate_image>', '', response_text, flags=re.DOTALL).strip()
            final_reply = response_text
            break

        raw_json = tool_call_match.group(1).strip()
        try:
            tool_data = json.loads(raw_json)
            tname = tool_data.get("name")
            targs = tool_data.get("arguments", {})
        except Exception as e:
            logger.warning(f"Tool parse error: {e}")
            final_reply = response_text
            break

        logger.info(f"Executing: {tname} -> {targs}")
        tresult = ""

        if tname == "execute_code":
            tresult = tool_execute_code(targs.get("code", ""))
        elif tname == "web_search":
            tresult = tool_web_search(targs.get("query", ""))
        elif tname == "fetch_url":
            tresult = tool_fetch_url(targs.get("url", ""))
        elif tname == "generate_image":
            p = targs.get("prompt", "")
            generated_images.append(p)
            tresult = f"Image generation requested: {p}"
        elif tname == "get_crypto_price":
            tresult = tool_get_crypto(targs.get("coin", "bitcoin"))
        elif tname == "get_weather":
            tresult = tool_get_weather(targs.get("city", "Delhi"))
        elif tname == "generate_qr":
            qdata = targs.get("data", "")
            generated_qrs.append(qdata)
            tresult = f"QR code generated for: {qdata}"
        elif tname == "export_file":
            fn = targs.get("filename", "script.py")
            fc = targs.get("content", "")
            generated_files.append({"filename": fn, "content": fc})
            tresult = f"File '{fn}' created."
        elif tname == "create_project_zip":
            zname = targs.get("zip_name", "project.zip")
            zfiles = targs.get("files", {})
            generated_zips.append({"zip_name": zname, "files": zfiles})
            tresult = f"Project ZIP '{zname}' bundled with {len(zfiles)} files."
        elif tname == "remember_fact":
            tresult = tool_remember_fact(chat_id, targs.get("key", "info"), targs.get("value", ""))
        elif tname == "todo_manage":
            tresult = tool_todo_manage(chat_id, targs.get("action", "list"), targs.get("task", ""))
        else:
            tresult = f"Unknown tool: {tname}"

        messages.append({"role": "assistant", "content": response_text})
        messages.append({
            "role": "user",
            "content": f"<tool_response>\n{{\"name\": \"{tname}\", \"result\": {json.dumps(tresult)}}}\n</tool_response>"
        })

    clean_reply = re.sub(r'<thought>.*?</thought>', '', final_reply, flags=re.DOTALL).strip()
    clean_reply = re.sub(r'<tool_call>.*?</tool_call>', '', clean_reply, flags=re.DOTALL).strip()
    if not clean_reply:
        clean_reply = final_reply

    save_message_history(chat_id, "assistant", clean_reply)
    
    artifacts = {
        "images": generated_images,
        "files": generated_files,
        "qrs": generated_qrs,
        "zips": generated_zips
    }
    return clean_reply, artifacts


# ----------------- VISION ENGINE ----------------- #
def analyze_vision_image(image_bytes: bytes, caption: str = "") -> str:
    try:
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = caption if caption else "Analyze this image in detail and describe what you see."
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }
            ],
            max_tokens=1500
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Vision error: {e}")
        return "❌ Photo analyze karne me dikkat aayi."


# ----------------- NATURAL INTENT DETECTORS ----------------- #
IMAGE_KEYWORDS = ["photo", "image", "pic", "picture", "wallpaper", "portrait", "dp"]
ACTION_KEYWORDS = ["bhej", "vej", "banao", "dikhao", "generate", "send", "draw", "render", "create", "nikal", "do", "de"]

def detect_natural_image(text: str) -> str | None:
    t = text.strip().lower()
    if any(k in t for k in IMAGE_KEYWORDS) and any(a in t for a in ACTION_KEYWORDS):
        cleaned = re.sub(r'\b(photo|image|picture|pic|wallpaper|portrait|bhej|vej|banao|dikhao|generate|send|draw|create|karo|kar|do|de|toh|na|mujhe|tum|uska|unki|unka|ek|ki|ka|ke|please|bhai)\b', ' ', t, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return f"{cleaned} portrait photograph, 8k resolution, cinematic lighting, photorealistic" if len(cleaned) >= 2 else "beautiful cinematic 8k portrait"
    return None

def detect_qr_intent(text: str) -> str | None:
    t = text.strip().lower()
    if "qr" in t and ("banao" in t or "generate" in t or "create" in t or "code" in t):
        cleaned = re.sub(r'\b(qr|code|banao|generate|karo|create|ka|ki|ke|for|link|please|bhai)\b', ' ', t, flags=re.IGNORECASE).strip()
        return cleaned if len(cleaned) > 2 else "https://telegram.org"
    return None

def detect_crypto_intent(text: str) -> str | None:
    t = text.strip().lower()
    crypto_coins = ["bitcoin", "btc", "ethereum", "eth", "solana", "sol", "doge", "dogecoin", "shiba", "xrp", "cardano"]
    for coin in crypto_coins:
        if coin in t and ("price" in t or "rate" in t or "kitna" in t or "bhav" in t or "value" in t):
            name_map = {"btc": "bitcoin", "eth": "ethereum", "sol": "solana", "doge": "dogecoin", "shib": "shiba-inu"}
            return name_map.get(coin, coin)
    return None

def detect_weather_intent(text: str) -> str | None:
    t = text.strip().lower()
    if "weather" in t or "mausam" in t or "temperature" in t:
        cleaned = re.sub(r'\b(weather|mausam|temperature|kya|hai|batao|ka|ki|ke|in|city|today|aaj)\b', ' ', t, flags=re.IGNORECASE).strip()
        return cleaned if len(cleaned) >= 2 else "Patna"
    return None

def detect_voice_intent(text: str) -> bool:
    t = text.strip().lower()
    return any(p in t for p in ["bol kar", "bolke", "voice note", "audio me", "audio sunao", "sunao"])


# ----------------- INLINE KEYBOARDS & UI ----------------- #
def create_action_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    btn_voice = InlineKeyboardButton("🔊 Bol Kar Sunao", callback_data="tts_last")
    btn_clear = InlineKeyboardButton("🧹 Clear Memory", callback_data="clear_mem")
    markup.row(btn_voice, btn_clear)
    return markup


# ----------------- MESSAGE SENDER & DISPATCHER ----------------- #
def send_agent_response(chat_id: int, text: str, artifacts: dict, reply_to_id: int | None = None, send_audio: bool = False):
    # 1. Send Text / Code with Action Keyboard
    if text:
        markup = create_action_keyboard(chat_id)
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

    # 2. Send Audio if requested
    if send_audio and text:
        bot.send_chat_action(chat_id, 'record_audio')
        audio_bio = tool_text_to_speech(text)
        if audio_bio:
            bot.send_voice(chat_id, audio_bio, caption="🎙️ *Lexi Lore Spoken Audio*", parse_mode="Markdown")

    # 3. Send Images
    for img_p in artifacts.get("images", []):
        bot.send_chat_action(chat_id, 'upload_photo')
        img_bio = tool_generate_image(img_p)
        if img_bio:
            bot.send_photo(chat_id, img_bio, caption=f"🎨 *Generated:* `{img_p[:90]}`", parse_mode="Markdown")

    # 4. Send QR Codes
    for qr_d in artifacts.get("qrs", []):
        bot.send_chat_action(chat_id, 'upload_photo')
        q_bio = tool_generate_qr(qr_d)
        if q_bio:
            bot.send_photo(chat_id, q_bio, caption=f"📱 *QR Code:* `{qr_d[:90]}`", parse_mode="Markdown")

    # 5. Send Files
    for fo in artifacts.get("files", []):
        fn = fo.get("filename", "code.py")
        fc = fo.get("content", "")
        fbio = io.BytesIO(fc.encode('utf-8'))
        fbio.name = fn
        bot.send_document(chat_id, fbio, caption=f"📁 *Generated File:* `{fn}`", parse_mode="Markdown")

    # 6. Send Project ZIPs
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


# ----------------- CALLBACK QUERY HANDLER (Buttons) ----------------- #
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    if call.data == "tts_last":
        bot.answer_callback_query(call.id, "Voice generate ho rahi hai...")
        bot.send_chat_action(chat_id, 'record_audio')
        # Get last assistant message
        history = get_chat_history(chat_id, limit=2)
        last_text = ""
        for h in reversed(history):
            if h["role"] == "assistant":
                last_text = h["content"]
                break
        if last_text:
            abio = tool_text_to_speech(last_text)
            if abio:
                bot.send_voice(chat_id, abio, caption="🎙️ *Spoken Voice Note*", parse_mode="Markdown")
    elif call.data == "clear_mem":
        clear_chat_memory(chat_id)
        bot.answer_callback_query(call.id, "Memory clear ho gayi!")
        bot.send_message(chat_id, "🧹 Conversation history cleared.")


# ----------------- TELEGRAM COMMANDS ----------------- #

@bot.message_handler(commands=['start'])
def cmd_start(message):
    welcome = (
        "⚡ *Nous Hermes Ultra Autonomous Agent (Lexi Lore)* ⚡\n\n"
        "Main ab **Multi-Advanced Mode** me chal raha hoon! Kisi command ki zaroorat nahi, direct chat karein:\n\n"
        "🌟 *Superpowers:*\n"
        "• 🌐 **Live Web Search:** Internet se taaza khabar aur data nikalna.\n"
        "• 💻 **Terminal Python Sandbox:** Code run karke live output nikalna.\n"
        "• 🎨 **Flux HD Image:** _'Sunny Leone ki photo bhej'_ ya _'Cyberpunk car banao'_\n"
        "• 🎙️ **Voice Notes:** _'Bol kar sunao'_ bolne par audio voice note bhejna.\n"
        "• 📊 **Live Crypto & Weather:** Bitcoin price aur kisi bhi city ka live mausam.\n"
        "• 📱 **QR Generator:** Kisi bhi link ya text ka instant QR code.\n"
        "• 📦 **ZIP Project Exporter:** Pure project files ko zip bana kar bhejna.\n"
        "• 👁️ **Vision:** Mujhe koi bhi photo bhej kar sawal pucho!"
    )
    bot.reply_to(message, welcome, parse_mode="Markdown")


@bot.message_handler(commands=['voice', 'speak', 'audio'])
def cmd_voice(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "ℹ️ *Usage:* `/voice <kya bolna hai>`", parse_mode="Markdown")
        return
    text = args[1].strip()
    bot.send_chat_action(message.chat.id, 'record_audio')
    abio = tool_text_to_speech(text)
    if abio:
        bot.send_voice(message.chat.id, abio, caption=f"🎙️ `{text[:80]}`", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Audio generate karne me dikkat aayi.")


@bot.message_handler(commands=['qr'])
def cmd_qr(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "ℹ️ *Usage:* `/qr <link ya text>`", parse_mode="Markdown")
        return
    qbio = tool_generate_qr(args[1].strip())
    if qbio:
        bot.send_photo(message.chat.id, qbio, caption=f"📱 *QR Code for:* `{args[1].strip()}`", parse_mode="Markdown")


@bot.message_handler(commands=['crypto'])
def cmd_crypto(message):
    args = message.text.split(maxsplit=1)
    coin = args[1].strip() if len(args) > 1 else "bitcoin"
    res = tool_get_crypto(coin)
    bot.reply_to(message, res)


@bot.message_handler(commands=['weather'])
def cmd_weather(message):
    args = message.text.split(maxsplit=1)
    city = args[1].strip() if len(args) > 1 else "Patna"
    res = tool_get_weather(city)
    bot.reply_to(message, res)


@bot.message_handler(commands=['clear'])
def cmd_clear(message):
    clear_chat_memory(message.chat.id)
    bot.reply_to(message, "🧹 Memory clear ho gayi!")


@bot.message_handler(commands=['reset'])
def cmd_reset(message):
    reset_all_data(message.chat.id)
    bot.reply_to(message, "🔄 Bot reset to pure Blank Slate.")


# ----------------- PHOTO / VISION HANDLER ----------------- #
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    caption = message.caption or "Analyze this image and explain what is inside."
    bot.send_chat_action(chat_id, 'typing')
    try:
        finfo = bot.get_file(message.photo[-1].file_id)
        dfile = bot.download_file(finfo.file_path)
        v_res = analyze_vision_image(dfile, caption)
        bot.reply_to(message, v_res, reply_markup=create_action_keyboard(chat_id))
    except Exception as e:
        logger.error(f"Photo error: {e}")
        bot.reply_to(message, "❌ Photo analyze nahi ho payi.")


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
            rep, art = run_hermes_agent_loop(chat_id, prompt)
            send_agent_response(chat_id, rep, art, message.message_id)
            return
        bot.reply_to(message, "📁 File received.")
    except Exception as e:
        logger.error(f"Doc error: {e}")
        bot.reply_to(message, "❌ File read karne me dikkat aayi.")


# ----------------- NATURAL CONVERSATION ROUTER ----------------- #
@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_natural_chat(message):
    chat_id = message.chat.id
    user_text = message.text.strip()
    if not user_text:
        return

    # 1. Natural Image Generation
    img_p = detect_natural_image(user_text)
    if img_p:
        bot.send_chat_action(chat_id, 'upload_photo')
        ibio = tool_generate_image(img_p)
        if ibio:
            bot.send_photo(chat_id, ibio, caption=f"🎨 *Generated:* `{img_p[:90]}`", parse_mode="Markdown")
            return

    # 2. Natural QR Code Request
    qr_data = detect_qr_intent(user_text)
    if qr_data:
        bot.send_chat_action(chat_id, 'upload_photo')
        qbio = tool_generate_qr(qr_data)
        if qbio:
            bot.send_photo(chat_id, qbio, caption=f"📱 *QR Code:* `{qr_data}`", parse_mode="Markdown")
            return

    # 3. Natural Crypto Price
    crypto_coin = detect_crypto_intent(user_text)
    if crypto_coin:
        c_res = tool_get_crypto(crypto_coin)
        bot.reply_to(message, c_res)
        return

    # 4. Natural Weather
    city_name = detect_weather_intent(user_text)
    if city_name and len(user_text.split()) < 7:
        w_res = tool_get_weather(city_name)
        bot.reply_to(message, w_res)
        return

    # 5. Check if user asked for Spoken Audio response
    wants_voice = detect_voice_intent(user_text)

    # 6. Natural Clear/Reset
    if any(p in user_text.lower() for p in ["pichli baatein bhul jao", "memory clear karo", "chat clear karo"]):
        clear_chat_memory(chat_id)
        bot.reply_to(message, "🧹 Pichli baatein bhul gaya hoon!")
        return

    # 7. Agentic Multi-Step Loop
    bot.send_chat_action(chat_id, 'typing')
    reply, artifacts = run_hermes_agent_loop(chat_id, user_text)
    send_agent_response(chat_id, reply, artifacts, message.message_id, send_audio=wants_voice)


# ----------------- MAIN STARTUP ----------------- #
if __name__ == "__main__":
    logger.info("Starting Nous Hermes Ultra Autonomous Agent...")
    print("🚀 Hermes Ultra Agent is ONLINE! Web, Sandbox, Vision, Voice, Crypto & QR Enabled.")
    bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)
