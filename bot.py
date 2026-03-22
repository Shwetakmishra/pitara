import os
import anthropic
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    
    response = claude.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system="""You are Pitara, a warm and curious personal assistant. 
        The user is sharing things that caught their interest today.
        Respond briefly and thoughtfully. Ask one follow up question 
        to help them think deeper about what they shared.""",
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