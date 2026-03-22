import os
import base64
import json
from datetime import datetime
import anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

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


# ── per-user conversation history (in-memory, resets on restart) ──────────

conversation_histories: dict = {}


def get_history(user_id: int) -> list:
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []
    return conversation_histories[user_id]


def add_to_history(user_id: int, role: str, content: str) -> None:
    get_history(user_id).append({"role": role, "content": content})
    conversation_histories[user_id] = conversation_histories[user_id][-20:]


def clear_history(user_id: int) -> None:
    conversation_histories[user_id] = []


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text

    # Trigger: reflection on past entries (bypasses conversation history)
    if user_message.strip().lower() == "what have i been thinking about?":
        memory = load_memory()
        if not memory["entries"]:
            await update.message.reply_text("No memories yet — start sharing things with me!")
            return
        entries_text = "\n".join(
            f"{i+1}. [{e['timestamp']}] ({e['type']}) {e['content']}"
            for i, e in enumerate(memory["entries"])
        )
        response = claude.messages.create(
            model=MODEL,
            max_tokens=1024,
            system="You are a reflective assistant.",
            messages=[{
                "role": "user",
                "content": f"{entries_text}\n\nLooking at these entries, what themes and patterns do you notice in what I've been thinking about?"
            }]
        )
        await update.message.reply_text(response.content[0].text)
        return

    # Normal message — pass full history to Claude
    history = get_history(user_id)
    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=history + [{"role": "user", "content": user_message}]
    )
    reply = response.content[0].text
    await update.message.reply_text(reply)
    add_to_history(user_id, "user", user_message)
    add_to_history(user_id, "assistant", reply)
    save_entry("text", user_message, reply)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id

        # Download highest-resolution photo (last in list)
        photo = update.message.photo[-1]
        file = await photo.get_file()
        photo_bytes = await file.download_as_bytearray()
        image_data = base64.standard_b64encode(bytes(photo_bytes)).decode("utf-8")

        caption = update.message.caption
        user_text = f"I sent this with the caption: {caption}. " if caption else ""
        user_text += "Please describe what you see in this image and ask me one question about what caught my attention."

        history = get_history(user_id)
        response = claude.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=history + [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }]
        )
        reply = response.content[0].text
        await update.message.reply_text(reply)

        # Store text placeholder in history (not raw image bytes)
        description = caption if caption else reply
        truncated = description[:80] + ("..." if len(description) > 80 else "")
        placeholder = f'[sent an image: "{truncated}"]'
        add_to_history(user_id, "user", placeholder)
        add_to_history(user_id, "assistant", reply)

        save_entry("image", description, reply)

    except Exception as e:
        await update.message.reply_text("Sorry, I had trouble processing that image. Try again?")
        raise


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_history(user_id)
    await update.message.reply_text("Starting a fresh page ✨")


if __name__ == "__main__":
    print("Pitara is waking up...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler(["new", "clear"], handle_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Pitara is running. Open Telegram and say something.")
    app.run_polling()