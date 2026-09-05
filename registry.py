import io
import re
import sys
import os
import json
import urllib.parse
import subprocess
import zipfile
import requests
import qrcode
from gtts import gTTS
import logging
from memory.store import save_fact, DB_PATH
from cron.scheduler import add_cron_job, list_cron_jobs
import sqlite3

logger = logging.getLogger(__name__)

# ----------------- TOOL REGISTRY SPECIFICATIONS ----------------- #

TOOL_DEFINITIONS = """
### ACTIVE HERMES BUILT-IN TOOLS:
1. `execute_code`: Run Python scripts in local sandbox terminal with full FFmpeg, OpenCV, and system toolchain support.
   Format: <tool_call>{"name": "execute_code", "arguments": {"code": "import math; print(math.pi)"}}</tool_call>

2. `install_package`: Dynamically install ANY python package via pip at runtime without redeploying.
   Format: <tool_call>{"name": "install_package", "arguments": {"package": "pandas"}}</tool_call>

3. `web_search`: Live search the internet for real-time data, news, docs.
   Format: <tool_call>{"name": "web_search", "arguments": {"query": "python news"}}</tool_call>

4. `fetch_url`: Scrape text from any website or API.
   Format: <tool_call>{"name": "fetch_url", "arguments": {"url": "https://example.com"}}</tool_call>

5. `generate_image`: Draw 8K photorealistic HD images via Flux.
   Format: <tool_call>{"name": "generate_image", "arguments": {"prompt": "cyberpunk city"}}</tool_call>

6. `generate_video`: Generate AI video animation clips from prompt.
   Format: <tool_call>{"name": "generate_video", "arguments": {"prompt": "cyberpunk car driving in neon rain"}}</tool_call>

7. `get_crypto_price`: Live price of bitcoin, ethereum, solana, doge, etc.
   Format: <tool_call>{"name": "get_crypto_price", "arguments": {"coin": "bitcoin"}}</tool_call>

8. `get_weather`: Live weather and temperature for any city.
   Format: <tool_call>{"name": "get_weather", "arguments": {"city": "Patna"}}</tool_call>

9. `generate_qr`: Create a QR code for link, text, or UPI ID.
   Format: <tool_call>{"name": "generate_qr", "arguments": {"data": "https://telegram.org"}}</tool_call>

10. `export_file`: Create and send a downloadable code file (.py, .js, .html, .sh, .json).
    Format: <tool_call>{"name": "export_file", "arguments": {"filename": "bot.py", "content": "..."}}</tool_call>

11. `create_project_zip`: Create a zip bundle for full-stack multi-file projects.
    Format: <tool_call>{"name": "create_project_zip", "arguments": {"zip_name": "app.zip", "files": {"main.py": "...", "requirements.txt": "..."}}}</tool_call>

12. `remember_fact`: Store an important user preference into permanent memory.
    Format: <tool_call>{"name": "remember_fact", "arguments": {"key": "role", "value": "Python Dev"}}</tool_call>

13. `kanban_task`: Manage tasks and todos (actions: add, list, complete).
    Format: <tool_call>{"name": "kanban_task", "arguments": {"action": "add", "task": "Build UI"}}</tool_call>

14. `cron_schedule`: Schedule a proactive reminder/task in minutes.
    Format: <tool_call>{"name": "cron_schedule", "arguments": {"task": "Check server", "minutes": 10}}</tool_call>
"""

def exec_pip_install(package: str) -> str:
    """Installs any python package dynamically at runtime."""
    pkg_clean = re.sub(r'[^a-zA-Z0-9_\-<=>.]', '', package.strip())
    if not pkg_clean:
        return "Invalid package name."
    try:
        logger.info(f"Dynamically installing pip package: {pkg_clean}")
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", pkg_clean],
            capture_output=True,
            text=True,
            timeout=90
        )
        if res.returncode == 0:
            return f"✅ Package '{pkg_clean}' successfully installed and ready to import!"
        else:
            return f"❌ Pip install error for '{pkg_clean}':\n{res.stderr[:1000]}"
    except subprocess.TimeoutExpired:
        return f"Timeout installing '{pkg_clean}' (took longer than 90 seconds)."
    except Exception as e:
        return f"Install error: {e}"

def exec_python_code(code: str) -> str:
    try:
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)
        out = res.stdout
        if res.stderr:
            # Check if ModuleNotFoundError and attempt auto-fix hint
            out += f"\nSTDERR:\n{res.stderr}"
        return out[:3000] if out.strip() else "Executed successfully (zero output)."
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out (20s limit)."
    except Exception as e:
        return f"Execution error: {e}"

def exec_web_search(query: str) -> str:
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

def exec_fetch_url(url: str) -> str:
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

def exec_generate_image(prompt: str) -> io.BytesIO | None:
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

def exec_crypto(coin: str) -> str:
    try:
        c_clean = coin.strip().lower()
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={c_clean}&vs_currencies=usd,inr"
        r = requests.get(url, timeout=8).json()
        if c_clean in r:
            usd = r[c_clean].get('usd', 'N/A')
            inr = r[c_clean].get('inr', 'N/A')
            return f"{coin.upper()} Price:\n💵 USD: ${usd:,}\n🇮🇳 INR: ₹{inr:,}"
        return f"Could not find price for '{coin}'."
    except Exception as e:
        return f"Crypto API error: {e}"

def exec_weather(city: str) -> str:
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
            return f"🌤️ Weather in {cname}, {country}:\n🌡️ Temp: {temp}°C | 💨 Wind: {wind} km/h"
        return f"City '{city}' not found."
    except Exception as e:
        return f"Weather API error: {e}"

def exec_qr(data: str) -> io.BytesIO | None:
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

def exec_tts(text: str) -> io.BytesIO | None:
    try:
        clean = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        clean = re.sub(r'[`*_~#]', '', clean).strip()
        if not clean:
            clean = "Here is your response."
        tts = gTTS(text=clean[:500], lang='hi')
        bio = io.BytesIO()
        tts.write_to_fp(bio)
        bio.name = "voice_note.mp3"
        bio.seek(0)
        return bio
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None

def exec_kanban(chat_id: int, action: str, task: str = "") -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if action == "add" and task:
        cur.execute("INSERT INTO kanban_tasks (chat_id, task) VALUES (?, ?)", (chat_id, task))
        conn.commit()
        msg = f"Task created: '{task}'"
    elif action == "list":
        cur.execute("SELECT id, task, status FROM kanban_tasks WHERE chat_id = ? AND status != 'completed'", (chat_id,))
        rows = cur.fetchall()
        msg = "📋 Active Tasks:\n" + "\n".join([f"• [{r[0]}] {r[1]} ({r[2]})" for r in rows]) if rows else "No open tasks."
    elif action == "complete" and task:
        cur.execute("UPDATE kanban_tasks SET status = 'completed' WHERE chat_id = ? AND (task LIKE ? OR id = ?)", (chat_id, f"%{task}%", task))
        conn.commit()
        msg = f"Task marked complete: {task}"
    else:
        msg = "Unknown task action."
    conn.close()
    return msg
