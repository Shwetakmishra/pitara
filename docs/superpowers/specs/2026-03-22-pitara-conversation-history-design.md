# Pitara: Multi-Turn Conversation History — Design Spec

**Date:** 2026-03-22
**Scope:** Add per-user in-memory conversation history to `bot.py`

---

## Overview

Currently every message Pitara handles is stateless — Claude has no context from prior turns. This spec adds a per-user conversation history stored in a module-level Python dict. The history is passed to Claude on every message so it can follow the thread of a conversation. It resets when the bot restarts or when the user sends `/new` or `/clear`.

All changes are confined to `bot.py`. No new files are added.

---

## Data Structure

```python
conversation_histories: dict = {}
# Shape: { user_id (int): [ {"role": "user"|"assistant", "content": str} ] }
```

Lives at module level. Cleared when the process restarts (intentional — history is session-scoped, not persistent).

---

## Helper Functions

| Function | Signature | Behaviour |
|---|---|---|
| `get_history` | `(user_id: int) -> list` | Returns the history list for that user, creating an empty list if absent |
| `add_to_history` | `(user_id: int, role: str, content: str) -> None` | Appends `{"role": role, "content": content}`, then trims list to last 20 entries (`[-20:]`) |
| `clear_history` | `(user_id: int) -> None` | Sets `conversation_histories[user_id] = []` |

The 20-message sliding window is applied inside `add_to_history` after every append.

---

## Handler Changes

### `handle_message`

1. Get `user_id = update.effective_user.id`
2. Check for trigger phrase `"what have i been thinking about?"` (existing logic):
   - If matched: process as before, **do not add to history**, return
3. For normal messages:
   - Fetch history: `history = get_history(user_id)`
   - Build messages list: `history + [{"role": "user", "content": user_message}]`
   - Call `claude.messages.create(model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT, messages=...)`
   - Call `add_to_history(user_id, "user", user_message)`
   - Call `add_to_history(user_id, "assistant", reply)`
   - Call `save_entry(...)` as before

### `handle_photo`

1. Get `user_id = update.effective_user.id`
2. Download photo, build image content block (existing logic)
3. Fetch history: `history = get_history(user_id)`
4. Build messages list: `history + [{"role": "user", "content": [image_block, text_block]}]`
5. Call Claude with that messages list
6. After reply:
   - Build text placeholder: `f'[sent an image: "{caption}"]'` if caption, else `f'[sent an image: "{reply[:80]}..."]'`
   - Call `add_to_history(user_id, "user", placeholder)`
   - Call `add_to_history(user_id, "assistant", reply)`
   - Call `save_entry(...)` as before

### `handle_clear` (new)

```python
async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_history(user_id)
    await update.message.reply_text("Starting a fresh page ✨")
```

Registered for both `/new` and `/clear` commands.

---

## Registration

```python
from telegram.ext import CommandHandler

app.add_handler(CommandHandler(["new", "clear"], handle_clear))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
```

`CommandHandler` is added before the text handler so commands are not accidentally caught by `filters.TEXT & ~filters.COMMAND` (which already excludes commands via `~filters.COMMAND`).

---

## History Limit

20 messages per user. Applied as a sliding window: oldest messages are dropped after every append. A full back-and-forth exchange is 2 messages (1 user + 1 assistant), so 20 messages = 10 full exchanges.

---

## Error Handling

- No new error handling needed: history helpers are pure Python dict operations and cannot fail
- If `update.effective_user` is `None` (edge case for certain Telegram message types), `get_history` would raise `AttributeError` — acceptable since this scenario cannot arise for text or photo messages from real users

---

## Out of Scope

- Persisting history to disk across restarts
- Per-user history for the "what have i been thinking about?" reflection trigger
- History for group chats (bot is single-user)
- Configurable history length
