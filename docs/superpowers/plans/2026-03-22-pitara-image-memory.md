# Pitara Image Support & Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add photo handling (Claude vision) and persistent memory logging to `bot.py`, plus a "what have I been thinking about?" reflection trigger.

**Architecture:** All logic stays in `bot.py`. Two new helper functions (`load_memory`, `save_entry`) manage a local `memory.json`. A new `handle_photo` handler downloads Telegram photos, base64-encodes them, and sends them to Claude. The existing `handle_message` gains a trigger-phrase check and a memory save on every response.

**Tech Stack:** python-telegram-bot, anthropic Python SDK, stdlib (`base64`, `json`, `datetime`)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `bot.py` | Modify | All bot logic — handlers, memory helpers, Claude calls |
| `memory.json` | Created at runtime | Persistent entry log (not a source file) |
| `tests/test_bot.py` | Create | Unit tests for memory helpers and handler logic |

---

### Task 1: Add imports, model constant, and memory helpers

**Files:**
- Modify: `bot.py:1-12`
- Create: `tests/test_bot.py`

- [ ] **Step 1: Write failing tests for `load_memory` and `save_entry`**

Create `tests/test_bot.py`:

```python
import json
import os
import tempfile
import pytest
from unittest.mock import patch
from datetime import datetime

# We'll import from bot after patching the memory path
import importlib


def make_bot(memory_path):
    """Re-import bot with MEMORY_FILE patched to a temp path."""
    import bot
    bot.MEMORY_FILE = memory_path
    return bot


def test_load_memory_missing_file(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")
    result = bot.load_memory()
    assert result == {"entries": []}


def test_load_memory_existing_file(tmp_path):
    import bot
    path = tmp_path / "memory.json"
    data = {"entries": [{"timestamp": "2026-03-22 10:00", "type": "text", "content": "hello", "claude_response": "hi"}]}
    path.write_text(json.dumps(data))
    bot.MEMORY_FILE = str(path)
    result = bot.load_memory()
    assert result == data


def test_save_entry_creates_file(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")
    bot.save_entry("text", "I saw a bird", "That sounds wonderful!")
    data = json.loads((tmp_path / "memory.json").read_text())
    assert len(data["entries"]) == 1
    entry = data["entries"][0]
    assert entry["type"] == "text"
    assert entry["content"] == "I saw a bird"
    assert entry["claude_response"] == "That sounds wonderful!"
    assert "timestamp" in entry


def test_save_entry_appends(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")
    bot.save_entry("text", "first", "reply1")
    bot.save_entry("image", "second", "reply2")
    data = json.loads((tmp_path / "memory.json").read_text())
    assert len(data["entries"]) == 2
    assert data["entries"][0]["content"] == "first"
    assert data["entries"][1]["type"] == "image"


def test_save_entry_timestamp_format(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")
    bot.save_entry("text", "test", "response")
    data = json.loads((tmp_path / "memory.json").read_text())
    ts = data["entries"][0]["timestamp"]
    # Should parse without error
    datetime.strptime(ts, "%Y-%m-%d %H:%M")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/sunstone/pitara
python -m pytest tests/test_bot.py -v
```

Expected: `ImportError` or `AttributeError` — `MEMORY_FILE`, `load_memory`, `save_entry` don't exist yet.

- [ ] **Step 3: Add imports, model constant, MEMORY_FILE, and helper functions to `bot.py`**

Replace the top of `bot.py` (lines 1–12) with:

```python
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

SYSTEM_PROMPT = """You are Pitara, a warm and curious personal assistant.
The user is sharing things that caught their interest today.
Respond briefly and thoughtfully. Ask one follow up question
to help them think deeper about what they shared."""


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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_bot.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add memory helpers and model constant to bot.py"
```

---

### Task 2: Update `handle_message` with trigger-phrase check and memory save

**Files:**
- Modify: `bot.py` — `handle_message` function
- Modify: `tests/test_bot.py` — add handler tests

- [ ] **Step 1: Write failing tests for updated `handle_message`**

Add to `tests/test_bot.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_handle_message_saves_to_memory(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")

    update = MagicMock()
    update.message.text = "I found a cool moss formation"
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch.object(bot.claude.messages, "create") as mock_create:
        mock_create.return_value.content = [MagicMock(text="Moss is amazing! What drew you to it?")]
        await bot.handle_message(update, context)

    data = json.loads((tmp_path / "memory.json").read_text())
    assert len(data["entries"]) == 1
    assert data["entries"][0]["type"] == "text"
    assert data["entries"][0]["content"] == "I found a cool moss formation"


@pytest.mark.asyncio
async def test_handle_message_trigger_empty_memory(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")

    update = MagicMock()
    update.message.text = "what have I been thinking about?"
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch.object(bot.claude.messages, "create") as mock_create:
        await bot.handle_message(update, context)
        mock_create.assert_not_called()

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "No memories yet" in call_text


@pytest.mark.asyncio
async def test_handle_message_trigger_with_entries(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")
    # Pre-populate memory
    data = {"entries": [{"timestamp": "2026-03-22 10:00", "type": "text", "content": "birds", "claude_response": "nice"}]}
    (tmp_path / "memory.json").write_text(json.dumps(data))

    update = MagicMock()
    update.message.text = "What have I been thinking about?"
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch.object(bot.claude.messages, "create") as mock_create:
        mock_create.return_value.content = [MagicMock(text="You seem interested in nature.")]
        await bot.handle_message(update, context)
        mock_create.assert_called_once()

    # Trigger response should NOT be saved to memory
    data_after = json.loads((tmp_path / "memory.json").read_text())
    assert len(data_after["entries"]) == 1  # still 1, not 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_bot.py::test_handle_message_saves_to_memory tests/test_bot.py::test_handle_message_trigger_empty_memory tests/test_bot.py::test_handle_message_trigger_with_entries -v
```

Expected: FAIL — `handle_message` doesn't yet save to memory or check for trigger phrase.

- [ ] **Step 3: Replace `handle_message` in `bot.py`**

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    # Trigger: reflection on past entries
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

    # Normal message
    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    reply = response.content[0].text
    await update.message.reply_text(reply)
    save_entry("text", user_message, reply)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_bot.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add trigger-phrase check and memory save to handle_message"
```

---

### Task 3: Add `handle_photo` handler

**Files:**
- Modify: `bot.py` — add `handle_photo` function and register it
- Modify: `tests/test_bot.py` — add photo handler tests

- [ ] **Step 1: Write failing tests for `handle_photo`**

Add to `tests/test_bot.py`:

```python
@pytest.mark.asyncio
async def test_handle_photo_no_caption(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")

    photo_mock = MagicMock()
    photo_mock.file_id = "abc123"
    file_mock = AsyncMock()
    file_mock.download_as_bytearray = AsyncMock(return_value=bytearray(b"fakejpegbytes"))
    photo_mock.get_file = AsyncMock(return_value=file_mock)

    update = MagicMock()
    update.message.photo = [photo_mock]
    update.message.caption = None
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch.object(bot.claude.messages, "create") as mock_create:
        mock_create.return_value.content = [MagicMock(text="I see a forest path. What drew you to photograph it?")]
        await bot.handle_photo(update, context)

    # Without caption, content saved should be Claude's description
    data = json.loads((tmp_path / "memory.json").read_text())
    assert len(data["entries"]) == 1
    entry = data["entries"][0]
    assert entry["type"] == "image"
    assert entry["content"] == "I see a forest path. What drew you to photograph it?"


@pytest.mark.asyncio
async def test_handle_photo_with_caption(tmp_path):
    import bot
    bot.MEMORY_FILE = str(tmp_path / "memory.json")

    photo_mock = MagicMock()
    file_mock = AsyncMock()
    file_mock.download_as_bytearray = AsyncMock(return_value=bytearray(b"fakejpegbytes"))
    photo_mock.get_file = AsyncMock(return_value=file_mock)

    update = MagicMock()
    update.message.photo = [photo_mock]
    update.message.caption = "morning light through the trees"
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with patch.object(bot.claude.messages, "create") as mock_create:
        mock_create.return_value.content = [MagicMock(text="Beautiful golden light! What time was this?")]
        await bot.handle_photo(update, context)

    # With caption, content saved should be the caption
    data = json.loads((tmp_path / "memory.json").read_text())
    entry = data["entries"][0]
    assert entry["content"] == "morning light through the trees"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_bot.py::test_handle_photo_no_caption tests/test_bot.py::test_handle_photo_with_caption -v
```

Expected: FAIL — `handle_photo` does not exist yet.

- [ ] **Step 3: Add `handle_photo` to `bot.py`**

Add after `handle_message`:

```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Download highest-resolution photo (last in list)
    photo = update.message.photo[-1]
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()
    image_data = base64.standard_b64encode(bytes(photo_bytes)).decode("utf-8")

    caption = update.message.caption
    user_text = f"I sent this with the caption: {caption}. " if caption else ""
    user_text += "Please describe what you see in this image and ask me one question about what caught my attention."

    response = claude.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{
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

    content = caption if caption else reply
    save_entry("image", content, reply)
```

- [ ] **Step 4: Register `handle_photo` in `__main__`**

Update the `if __name__ == "__main__":` block:

```python
if __name__ == "__main__":
    print("Pitara is waking up...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Pitara is running. Open Telegram and say something.")
    app.run_polling()
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/test_bot.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add handle_photo with Claude vision and memory logging"
```

---

### Task 4: Manual smoke test

- [ ] **Step 1: Start the bot**

```bash
cd /Users/sunstone/pitara
python bot.py
```

Expected output: `Pitara is waking up...` then `Pitara is running. Open Telegram and say something.`

- [ ] **Step 2: Send a text message**

Open Telegram, send any message to the bot. Verify:
- Bot replies with a thoughtful response and a follow-up question
- `memory.json` is created with one entry (check with `cat memory.json`)

- [ ] **Step 3: Send a photo without a caption**

Send a photo. Verify:
- Bot replies describing what it sees and asks a question
- `memory.json` has a new image entry; `content` field contains Claude's description

- [ ] **Step 4: Send a photo with a caption**

Send another photo with a caption. Verify:
- Bot replies as expected
- `memory.json` image entry `content` is the caption text

- [ ] **Step 5: Trigger the reflection**

Send: `what have I been thinking about?`
Verify:
- Bot replies with themes/patterns from the entries
- `memory.json` entry count is unchanged (reflection not saved)

- [ ] **Step 6: Test empty memory edge case**

Delete or rename `memory.json`, then send `what have I been thinking about?`
Verify: bot replies with `"No memories yet — start sharing things with me!"`
