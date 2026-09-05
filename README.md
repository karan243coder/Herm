# 🚀 Nous Hermes Ultra Autonomous Agent (Lexi Lore)

Full-stack autonomous multi-tool agent based on [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).  
Optimized for **Koyeb Free Tier (512MB RAM)** & **OpenRouter Free Tier**.

---

## 🌟 10+ Multi-Advanced Superpowers:

1. 🌐 **Live Web Search & Scraping (`web_search`, `fetch_url`):** Real-time internet search and article scrapers.
2. 💻 **Local Python Sandbox Runner (`execute_code`):** Runs scripts, tests logic, calculates complex math live.
3. 👁️ **Multimodal Vision Engine (`vision_analyze`):** Send photos/screenshots to the bot, and it inspects and explains them.
4. 🎙️ **Voice Notes & Audio Speech (`text_to_speech` / `/voice`):** Generates voice messages and speaks back to you.
5. 📊 **Live Crypto & Market Tracker (`get_crypto_price`):** Live Bitcoin, Ethereum, Solana, Dogecoin prices.
6. 🌤️ **Global Real-time Weather (`get_weather`):** Live weather, temperatures, and wind speed for any city.
7. 📱 **Instant QR Code Generator (`generate_qr`):** Creates QR codes for links, text, UPI payments, and WiFi.
8. 📦 **Multi-File Project ZIP Bundler (`create_project_zip`):** Bundles full projects (`main.py`, `config.py`, `utils.py`) into downloadable `.zip` files.
9. 📁 **Direct Script Exporter (`export_file`):** Generates single `.py`, `.html`, `.js` files sent directly to Telegram.
10. 🧠 **Cross-Session Honcho/SQLite Memory (`remember_fact`):** Remembers instructions, name, and facts across restarts.
11. 🔘 **Interactive Telegram UI Buttons:** Quick action buttons (`🔊 Bol Kar Sunao`, `🧹 Clear Memory`).
12. 🛡️ **Koyeb Port 8080 Auto Health Check:** Zero downtime, pass Koyeb health checks 24/7.

---

## 🤖 Natural Chat Examples:

| What you say | What Hermes Agent Does |
|---|---|
| *"Sunny Leone ki photo bhej"* | Generates HD photorealistic image via Flux |
| *"Bitcoin ka live price kya hai?"* | Fetches real-time crypto price from CoinGecko |
| *"Patna ka live mausam kaisa hai?"* | Fetches real-time temperature & forecast |
| *"https://github.com ka QR code banao"* | Generates downloadable QR code image |
| *"Python me Telegram bot ka script likh kar file export karo"* | Writes full code and sends as downloadable `.py` file |
| *"Ek full-stack login website ka project zip bana kar do"* | Creates multiple files and sends a `.zip` archive |
| *"Ye mujhe bol kar samjhao"* | Sends a spoken Telegram voice note |
| *Send any Photo/Screenshot* | Analyzes image with Vision model and replies |

---

## 🐳 Koyeb 1-Click Deployment:

1. Push all files to your GitHub repository:
   - `bot.py`
   - `Dockerfile`
   - `requirements.txt`
   - `.dockerignore`
   - `README.md`
2. Go to [Koyeb.com](https://app.koyeb.com):
   - Select your **GitHub Repo** -> Builder **Dockerfile** -> Service Type **Worker** (or Web).
   - Instance: `Eco - Free (512MB RAM)`.
3. Set 2 Environment Variables:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENROUTER_API_KEY`
4. Click **Deploy**! 🚀
