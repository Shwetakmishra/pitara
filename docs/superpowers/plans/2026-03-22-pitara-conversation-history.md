# Pitara: Conversation History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-user in-memory conversation history so Claude maintains context across turns of a conversation.

**Architecture:** A module-level dict `conversation_histories` maps user IDs to message lists. Three helper functions manage read/write/clear. Both text and photo handlers pass the history to Claude before each call and update it after; photos add a text placeholder rather than raw image bytes. `/new` and `/clear` commands reset a user's history.

**Tech Stack:** python-telegram-bot 22.7, anthropic 0.86.0, Python 3.14, pytest + pytest-asyncio

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `bot.py` | Modify | Add history dict + helpers, update both handlers, add `handle_clear`, update imports and registration |
| `tests/test_bot.py` | Modify | Add tests for helpers, updated handlers, and `handle_clear` |

---

### Task 1: Add `conversation_histories` dict and helper functions

**Files:**
- Modify: `bot.py` — add after `save_entry`, before `handle_message`
- Modify: `tests/test_bot.py` — append new tests

- [ ] **Step 1: Write failing tests**

Append to `tests/test_bot.py` (no new imports needed — json, pytest, MagicMock, AsyncMock, patch already imported):

```python
# ── conversation history helpers ──────────────────────────────────────────

def test_get_history_new_user():
    import bot
    bot.conversation_histories = {}
    result = bot.get_history(123)
    assert result == []


def test_get_history_existing_user():
    import bot
    bot.conversation_histories = {}
    bot.conversation_histories[42] = [{"role": "user", "content": "hi"}]
    result = bot.get_history(42)
    assert result == [{"role": "user", "content": "hi"}]


def test_add_to_history_appends():
    import bot
    bot.conversation_histories = {}
    bot.add_to_history(1, "user", "hello")
    bot.add_to_history(1, "assistant", "world")
    assert bot.conversation_histories[1] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]


def test_add_to_history_trims_to_20():
    import bot
    bot.conversation_histories = {}
    for i in range(22):
        bot.add_to_history(1, "user", f"msg {i}")
    assert len(bot.conversation_histories[1]) == 20
    assert bot.conversation_histories[1][0]["content"] == "msg 2"
    assert bot.conversation_histories[1][-1]["content"] == "msg 21"


def test_clear_history():
    import bot
    bot.conversation_histories = {}
    bot.add_to_history(5, "user", "hello")
    bot.clear_history(5)
    assert bot.conversation_histories[5] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_bot.py::test_get_history_new_user tests/test_bot.py::test_add_to_history_trims_to_20 tests/test_bot.py::test_clear_history -v
```

Expected: FAIL — `conversation_histories`, `get_history`, `add_to_history`, `clear_history` don't exist yet.

- [ ] **Step 3: Add dict and helpers to `bot.py`**

Add after `save_entry` (before `handle_message`):

```python
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
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/test_bot.py -v
```

Expected: all 15 tests PASS (10 existing + 5 new).

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add conversation history dict and helpers"
```

---

### Task 2: Update `handle_message` to pass and save history

**Files:**
- Modify: `bot.py` — `handle_message` function
- Modify: `tests/test_bot.py` — add 2 new tests

- [ ] **Step 1: Write failing tests**

Append to `tests/test_bot.py`:

```python
# ── handle_message with history ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_message_passes_history_to_claude(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")
    bot.conversation_histories = {}

    user_id = 42
    bot.add_to_history(user_id, "user", "I love sunsets")
    bot.add_to_history(user_id, "assistant", "They are magical")

    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = "I saw one today"
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch.object(bot.claude.messages, "create") as mock_create:
        mock_create.return_value.content = [MagicMock(text="What colours did you see?")]
        await bot.handle_message(update, context)

    call_messages = mock_create.call_args.kwargs["messages"]
    assert call_messages[0] == {"role": "user", "content": "I love sunsets"}
    assert call_messages[1] == {"role": "assistant", "content": "They are magical"}
    assert call_messages[2] == {"role": "user", "content": "I saw one today"}


@pytest.mark.asyncio
async def test_handle_message_adds_to_history(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")
    bot.conversation_histories = {}

    update = MagicMock()
    update.effective_user.id = 99
    update.message.text = "I found a cool moss formation"
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch.object(bot.claude.messages, "create") as mock_create:
        mock_create.return_value.content = [MagicMock(text="Moss is amazing!")]
        await bot.handle_message(update, context)

    history = bot.get_history(99)
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "I found a cool moss formation"}
    assert history[1] == {"role": "assistant", "content": "Moss is amazing!"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_bot.py::test_handle_message_passes_history_to_claude tests/test_bot.py::test_handle_message_adds_to_history -v
```

Expected: FAIL — `handle_message` doesn't use history yet.

- [ ] **Step 3: Update `handle_message` in `bot.py`**

Replace the existing `handle_message` with:

```python
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
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/test_bot.py -v
```

Expected: all 17 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: pass conversation history to Claude in handle_message"
```

---

### Task 3: Update `handle_photo` to save a text placeholder to history

**Files:**
- Modify: `bot.py` — `handle_photo` function
- Modify: `tests/test_bot.py` — add 2 new tests

- [ ] **Step 1: Write failing tests**

Append to `tests/test_bot.py`:

```python
# ── handle_photo with history ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_photo_adds_placeholder_no_caption(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")
    bot.conversation_histories = {}

    photo_mock = MagicMock()
    file_mock = AsyncMock()
    file_mock.download_as_bytearray = AsyncMock(return_value=bytearray(b"fakejpeg"))
    photo_mock.get_file = AsyncMock(return_value=file_mock)

    update = MagicMock()
    update.effective_user.id = 7
    update.message.photo = [photo_mock]
    update.message.caption = None
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch.object(bot.claude.messages, "create") as mock_create:
        mock_create.return_value.content = [MagicMock(text="A sunlit path through a forest.")]
        await bot.handle_photo(update, context)

    history = bot.get_history(7)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert "[sent an image:" in history[0]["content"]
    assert "sunlit path" in history[0]["content"]
    assert history[1] == {"role": "assistant", "content": "A sunlit path through a forest."}


@pytest.mark.asyncio
async def test_handle_photo_adds_placeholder_with_caption(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")
    bot.conversation_histories = {}

    photo_mock = MagicMock()
    file_mock = AsyncMock()
    file_mock.download_as_bytearray = AsyncMock(return_value=bytearray(b"fakejpeg"))
    photo_mock.get_file = AsyncMock(return_value=file_mock)

    update = MagicMock()
    update.effective_user.id = 8
    update.message.photo = [photo_mock]
    update.message.caption = "morning mist over the lake"
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch.object(bot.claude.messages, "create") as mock_create:
        mock_create.return_value.content = [MagicMock(text="Serene and still.")]
        await bot.handle_photo(update, context)

    history = bot.get_history(8)
    assert '[sent an image: "morning mist over the lake"]' in history[0]["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_bot.py::test_handle_photo_adds_placeholder_no_caption tests/test_bot.py::test_handle_photo_adds_placeholder_with_caption -v
```

Expected: FAIL — `handle_photo` doesn't update history yet.

- [ ] **Step 3: Update `handle_photo` in `bot.py`**

Replace the existing `handle_photo` with:

```python
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

        content = caption if caption else reply
        save_entry("image", content, reply)

    except Exception as e:
        await update.message.reply_text("Sorry, I had trouble processing that image. Try again?")
        raise
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/test_bot.py -v
```

Expected: all 19 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add history placeholder to handle_photo"
```

---

### Task 4: Add `handle_clear` command handler and register it

**Files:**
- Modify: `bot.py` — add `handle_clear`, update imports, update `__main__`
- Modify: `tests/test_bot.py` — add 2 new tests

- [ ] **Step 1: Write failing tests**

Append to `tests/test_bot.py`:

```python
# ── handle_clear ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_clear_resets_history():
    import bot
    bot.conversation_histories = {}

    user_id = 77
    bot.add_to_history(user_id, "user", "hello")
    bot.add_to_history(user_id, "assistant", "hi there")

    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot.handle_clear(update, context)

    assert bot.get_history(user_id) == []


@pytest.mark.asyncio
async def test_handle_clear_replies_warmly():
    import bot
    bot.conversation_histories = {}

    update = MagicMock()
    update.effective_user.id = 55
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot.handle_clear(update, context)

    update.message.reply_text.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "fresh" in reply.lower() or "✨" in reply
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_bot.py::test_handle_clear_resets_history tests/test_bot.py::test_handle_clear_replies_warmly -v
```

Expected: FAIL — `handle_clear` does not exist yet.

- [ ] **Step 3: Add `handle_clear` to `bot.py` and update imports + `__main__`**

Update the import line at the top to add `CommandHandler`:

```python
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
```

Add `handle_clear` after `handle_photo` (before `__main__`):

```python
async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_history(user_id)
    await update.message.reply_text("Starting a fresh page ✨")
```

Update the `__main__` block:

```python
if __name__ == "__main__":
    print("Pitara is waking up...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler(["new", "clear"], handle_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Pitara is running. Open Telegram and say something.")
    app.run_polling()
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/test_bot.py -v
```

Expected: all 21 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add /new and /clear command to reset conversation history"
```
