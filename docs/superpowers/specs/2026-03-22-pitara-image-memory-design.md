# Pitara: Image Support & Memory — Design Spec

**Date:** 2026-03-22
**Scope:** Add image handling and persistent memory logging to `bot.py`
**Assumption:** Single-user personal bot. All memory is written to a shared `memory.json` with no per-user isolation — this is a known constraint, not an oversight.

---

## Overview

Pitara currently handles text messages only. This spec covers two additions:

1. **Image support** — when a photo is sent, Pitara downloads it, encodes it, and sends it to Claude for visual understanding, then replies with what it sees and a follow-up question.
2. **Memory** — every user message (text or image) is logged to `memory.json`. A special trigger phrase surfaces themes and patterns across past entries.

All changes are confined to `bot.py`. No new source files are added (`memory.json` is a runtime data file, not a source file).

---

## Architecture

Single-file: `bot.py`
Persistent store: `memory.json` (created on first write, sits alongside `bot.py`)

### New functions

| Function | Purpose |
|---|---|
| `load_memory()` | Read `memory.json`; return `{"entries": []}` if absent |
| `save_entry(entry_type, content, claude_response)` | Append timestamped entry and rewrite file |

Note: the parameter is named `entry_type` (not `type`) to avoid shadowing the Python built-in.

### Handlers

| Handler | Filter | Behaviour |
|---|---|---|
| `handle_message` | `filters.TEXT & ~filters.COMMAND` | Modified: adds trigger-phrase check at top and memory save after reply |
| `handle_photo` | `filters.PHOTO` | New — download, base64, Claude vision, memory |

---

## Model

Both handlers use `claude-haiku-4-5` (matching the value already in `bot.py`), which supports multimodal (vision) input. The model string is defined once at the top of the file and reused across all Claude calls.

---

## Data Flow

### Text message

1. Strip and lower the message. Check if it matches `"what have i been thinking about?"`
   - **If yes:** load memory entries. If entries list is empty, reply with a canned message ("No memories yet — start sharing things with me!") and return without calling Claude. Otherwise, send entries to Claude for theme/pattern analysis, reply — **do not save to memory.**
   - **If no:** send to Claude, reply, call `save_entry(entry_type="text", content=user_message, claude_response=reply)`

### Image message

1. Download highest-resolution photo bytes via `get_file()` → `download_as_bytearray()`
2. Base64-encode bytes
3. Build Claude request:
   - `system`: same Pitara system prompt as text handler
   - `messages[0].content`: list with image content block (`type: base64, media_type: image/jpeg`) plus a text block instructing Claude to describe what it sees and ask what caught the user's attention. If a caption was provided, include it as additional context.
4. `filters.PHOTO` restricts to Telegram-compressed photos, which are always JPEG — hardcoding `image/jpeg` is safe here. This handler intentionally does **not** cover documents sent as images, GIFs, or stickers; those message types are out of scope.
5. Reply with Claude's response
6. `content` to save: caption if the user provided one, otherwise Claude's description (the intent is to capture what the image was about, since no user text exists)
7. Call `save_entry(entry_type="image", content=content_value, claude_response=reply)`

---

## Prompts

### Text handler system prompt
Unchanged from current `bot.py`:
> "You are Pitara, a warm and curious personal assistant. The user is sharing things that caught their interest today. Respond briefly and thoughtfully. Ask one follow up question to help them think deeper about what they shared."

### Image handler
- **System prompt:** same as text handler
- **User turn text block:** "Please describe what you see in this image and ask me one question about what caught my attention." If a caption is present, prepend: `"I sent this with the caption: {caption}. "`

### Memory trigger prompt
- **System prompt:** "You are a reflective assistant."
- **User turn:** A numbered list of past entries formatted as `[timestamp] (type) content`, followed by: "Looking at these entries, what themes and patterns do you notice in what I've been thinking about?"

---

## Memory Format

File: `memory.json`

```json
{
  "entries": [
    {
      "timestamp": "2026-03-22 14:30",
      "type": "text",
      "content": "what the user sent",
      "claude_response": "what Pitara said"
    },
    {
      "timestamp": "2026-03-22 14:35",
      "type": "image",
      "content": "user caption, or Claude's description if no caption",
      "claude_response": "what Pitara said"
    }
  ]
}
```

Timestamps use local system time (`datetime.now()`), format `"%Y-%m-%d %H:%M"`. Acceptable for personal use where bot and user are in the same timezone.

---

## Error Handling

- `load_memory()` catches `FileNotFoundError` and returns empty structure; other exceptions propagate
- Photo download errors surface to python-telegram-bot's default error handling (no special wrapping at this stage)
- `save_entry` does a full rewrite of `memory.json` on every call (simple, correct at personal-use scale; no atomicity guarantee needed)

---

## Known Constraints

- **Memory size:** No pruning or entry-count limit. If `memory.json` grows large (hundreds of entries), the full list is sent to Claude on the trigger phrase, which may eventually approach context limits or degrade output quality. The user is responsible for manually pruning the file if needed.
- **Single user:** All entries share one file; no per-user isolation.

---

## Out of Scope

- Conversation history / multi-turn context fed back into Claude (each message remains stateless)
- Memory pruning or limits on entry count
- Multiple users / per-user memory isolation
- Command handlers (`/start`, `/help`)
- Document images, GIFs, stickers (only `filters.PHOTO` is handled)
