# 🧠 Official Nous Research Hermes Agent (Full Architecture)

Based on [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).  
Optimized for **Koyeb Free Tier (512MB RAM)** & **OpenRouter Free Tier**.

---

## 🏗️ Repository Architecture:

```text
├── bot.py                  # Telegram Gateway & Health Check Server
├── agent/
│   ├── soul.py             # True Soul (DEFAULT_SOUL_MD) & Cognitive Directives
│   └── loop.py             # Recursive Multi-Turn Agentic Reasoning Loop
├── tools/
│   └── registry.py         # Full Tool Registry (Web, Sandbox, Media, Files, QR, Cron)
├── skills/
│   └── manager.py          # Progressive Disclosure Skills (Code, Security, Design)
├── memory/
│   └── store.py            # SQLite Cross-Session Long-Term Memory & Kanban
├── cron/
│   └── scheduler.py        # Background Proactive Reminders & Scheduler
├── providers/
│   └── router.py           # Zero-404 Dynamic OpenRouter Free Model Router
├── Dockerfile              # Koyeb Port 8080 Container
└── requirements.txt        # Lightweight Dependencies
```

---

## ⚡ Superpowers & Modalities:

1. 🌐 **Live Web Search & Scraping (`web_search`, `fetch_url`)**
2. 💻 **Local Python Sandbox Runner (`execute_code`)**
3. 👁️ **Multimodal Vision Engine (`vision_analyze`)**
4. 🎙️ **Voice Notes & Audio Speech (TTS Voice Note Generator)**
5. 📊 **Live Crypto & Market Tracker (`get_crypto_price`)**
6. 🌤️ **Global Real-time Weather (`get_weather`)**
7. 📱 **Instant QR Code Generator (`generate_qr`)**
8. 📦 **Multi-File Project ZIP Bundler (`create_project_zip`)**
9. 📁 **Direct Script Exporter (`export_file`)**
10. ⏰ **Cron Autonomous Reminders (`cron_schedule`)**
11. 🧠 **Cross-Session Honcho/SQLite Memory (`remember_fact`)**
12. 🔘 **Interactive Telegram UI Buttons (`🔊 Bol Kar Sunao`, `🧹 Clear Memory`)**
13. 🛡️ **Koyeb Port 8080 Auto Health Check** (24/7 Zero Downtime)

---

## 🐳 Koyeb Deployment:

1. Push all files and folders to your GitHub repository.
2. In [Koyeb.com](https://app.koyeb.com):
   - Select your repo -> Builder: `Dockerfile` -> Service Type: `Worker` (or Web).
   - Instance: `Eco - Free (512MB RAM)`.
3. Set Environment Variables:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENROUTER_API_KEY`
4. Click **Deploy**! 🚀
