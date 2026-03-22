# Pitara

*Hindi for treasure chest.*

A warm digital companion that lives in your Telegram and keeps 
everything that catches your attention so nothing gets lost.

---

## The story behind it

As a kid I loved scrapbooking.

Cutting out magazine pages, sticking things together, making 
vision boards out of whatever caught my eye. It was messy and 
slow and I loved it. Everything I cared about had a home.

Now I take photos and delete them for storage. I write things 
in my notes app and forget they exist. I save posts on Instagram 
and never go back. I have more ways to capture things than ever 
and somehow everything still gets lost.

Pitara is my attempt to bring that scrapbook back, but in the 
place I already live, which is my phone.

You send it anything. A thought on the metro. A photo of 
something beautiful. A line from a book. A place you want to 
remember. Pitara keeps it, reflects on it, and over time starts 
to notice what you are drawn to.

Not a productivity tool. Not an assistant. Just a quiet little 
treasure chest that remembers what you put inside it.

---

## What it does

- Receives text and photos on Telegram
- Responds like a thoughtful friend, not a productivity tool
- Saves everything to a personal memory log
- Finds connections across your entries when you ask
- Gets to know your taste over time

---

## Built with

- [Claude API](https://anthropic.com)
- [python-telegram-bot](https://python-telegram-bot.org) — the interface
- Python — the glue

---

## How it works
```
You send a message or photo on Telegram
        ↓
Pitara receives it via Telegram Bot API
        ↓
Claude processes it with your memory as context
        ↓
Pitara responds and saves the entry to memory.json
        ↓
Ask "what have I been thinking about?" 
and it connects the dots
```

---

## Setup

1. Clone the repo
2. Create a `.env` file:
```
TELEGRAM_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
```
3. Install dependencies:
```bash
pip install anthropic python-telegram-bot python-dotenv
```
4. Run:
```bash
python3 bot.py
```
5. Open Telegram, find your bot, and send it something 
   worth remembering.

---

## What is coming next

- Image understanding — send a photo, Pitara reflects on 
  what it sees
- Smarter memory — finds patterns across everything you 
  have ever saved
- Weekly reflection — a summary of what you have been 
  drawn to lately
- Place discovery — cafe and travel suggestions based on 
  your actual taste

---

## Built by

Shweta Kumari — Product Manager

[LinkedIn](https://www.linkedin.com/in/arshwetakumari/) ·
[GitHub](https://github.com/Shwetakmishra)