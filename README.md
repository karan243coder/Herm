# 🧠 Hermes 3 Telegram Bot (Unrestricted Coding + Free Image Gen)

Powered by **Nous Research Hermes 3** + **Flux Image Engine** + **OpenRouter Free Tier**.
Optimized for **Koyeb Eco Free Tier (512MB RAM)**.

---

## 🚀 Features:

1. **⚡ Unrestricted Coding Power:**
   - Real Nous Hermes 3 prompt architecture: No moralizing lectures, no lazy code truncations (`// rest of code here`), full end-to-end working code.
   - Dedicated `/code <prompt>` command for instant pure code output.

2. **🎨 Free Built-in Image Generator (`/image`):**
   - Direct integration with Flux image model.
   - 100% Free, unlimited, and requires **NO extra API key**.

3. **🎭 True Blank Slate / Self-Steerable:**
   - Give it any name, personality, job, or custom rules with `/setidentity`.
   - Naturally adapts and self-corrects based on user feedback.

4. **💾 SQLite Long-Term Memory (Ultra-Lightweight):**
   - Consumes only **~35MB RAM** out of Koyeb's 512MB RAM limit!
   - Persistent memory saves user identity even across Koyeb server restarts.

5. **🛡️ 100% Free Stack:**
   - Telegram Bot: Free (`@BotFather`)
   - OpenRouter API: Free (`nousresearch/hermes-3-llama-3.1-405b:free`)
   - Hosting: Free (`Koyeb 512MB RAM Worker`)
   - Image API: Free (`Flux Engine`)

---

## 🤖 Commands:

| Command | Description |
|---|---|
| `/start` | Bot welcome message & status |
| `/code <task>` | Pure unrestricted coding mode |
| `/image <prompt>` | Generate HD AI images |
| `/setidentity <rules>` | Assign custom name, role & personality |
| `/myidentity` | Check active persona |
| `/clear` | Clear chat history (Keeps persona safe) |
| `/reset` | Hard reset back to original Hermes Blank Slate |
| `/ping` | Test bot response & health |

---

## 🐳 Koyeb 1-Click Deployment:

1. Create a GitHub repository and upload these files:
   - `bot.py`
   - `Dockerfile`
   - `requirements.txt`
   - `.dockerignore`

2. Go to [Koyeb Dashboard](https://app.koyeb.com):
   - Click **Create App / Service** -> Select **GitHub**.
   - **Builder:** `Dockerfile`
   - **Service Type:** `Worker` (Important: Select Worker, not Web Service)
   - **Instance Size:** `Eco - Free (512MB RAM)`

3. Add Environment Variables:
   - `TELEGRAM_BOT_TOKEN`: Token from `@BotFather`
   - `OPENROUTER_API_KEY`: Key from [OpenRouter](https://openrouter.ai/keys)

4. Click **Deploy**! 🚀
