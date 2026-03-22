import json
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

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
