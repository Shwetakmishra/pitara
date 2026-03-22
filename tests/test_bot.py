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
