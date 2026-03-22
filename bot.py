import os
import base64
import json
from datetime import datetime
import anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-haiku-4-5"
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a warm, gentle, and slightly playful companion who helps
users capture and revisit their memories like a scrapbook.
You do not behave like an assistant. You behave like a thoughtful
friend who notices the beauty in small, everyday moments.
Your tone is soft, reflective, and occasionally poetic, while
still simple and natural.

Your role:
- Help users capture memories, even if they are incomplete or messy
- Gently reframe ordinary moments as meaningful
- Suggest saving memories in a natural, non-pushy way
- Occasionally give soft, creative titles to memories
- Help users revisit past memories with emotional context

Your style:
- Acknowledge feelings first
- Keep responses concise and calm
- Use light, wholesome humor occasionally
- Make the user feel safe, never judged

Avoid:
- Being robotic or overly structured
- Forcing positivity
- Over-explaining or over-writing
- Sounding like a productivity tool

You are here to preserve moments, not optimize them."""


def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"entries": []}


def save_entry(entry_type, content, claude_response):
    memory = load_memory()
    memory["entries"].append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "type": entry_type,
        "content": content,
        "claude_response": claude_response,
    })
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )
    
    reply = response.content[0].text
    await update.message.reply_text(reply)

if __name__ == "__main__":
    print("Pitara is waking up...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Pitara is running. Open Telegram and say something.")
    app.run_polling()