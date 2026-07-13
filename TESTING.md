# 🧪 Testing Guide

This document describes the manual tests used to validate Baton before deployment.

---

# Prerequisites

Before testing, ensure:

- Python 3.11+
- Dependencies installed
- Valid `.env` configuration
- Slack App installed
- Workspace contains sample conversations

Run the application:

```bash
python app.py
```

---

# Startup

| Test | Expected Result |
|------|-----------------|
| Start application | Application starts successfully |
| Missing environment variable | Clear startup error is displayed |
| Valid configuration | Socket Mode connects successfully |

---

# Assistant Experience

| Test | Expected Result |
|------|-----------------|
| Open new Assistant thread | Welcome message appears |
| Suggested prompts | Three prompts are displayed |
| Send empty message | No response |

---

# Question Answering

| Test | Expected Result |
|------|-----------------|
| Ask question with matching workspace data | AI returns answer with citations |
| Ask unrelated question | Reports that no relevant information exists |
| Ask broad question | Returns best available summary |

---

# Handover Generation

| Test | Expected Result |
|------|-----------------|
| Generate handover for mentioned user | Slack Canvas is created |
| Generate without mention | Uses requesting user |
| User has no history | Friendly "No messages found" response |

---

# Error Handling

| Test | Expected Result |
|------|-----------------|
| Invalid Groq API key | Friendly AI error message |
| Slack search unavailable | Graceful failure |
| Multiple rapid requests | Application remains stable |

---

# Edge Cases

| Test | Expected Result |
|------|-----------------|
| Emoji-only message | No crash |
| Long message | Processed safely |
| Special characters | No parsing issues |
| Conversation resumed later | Continues normally |

---

# Validation Scripts

Run the included validation scripts.

```bash
python spikes/groq_smoke.py
```

```bash
python spikes/rts_spike.py "How did we run the tournament?"
```

Expected outcome:

- Groq connectivity succeeds.
- Slack Real-Time Search returns results.
- No runtime errors.

---

# Success Criteria

Baton is considered ready when:

-  Starts without errors
-  Connects to Slack successfully
-  Answers questions using workspace history
-  Includes source citations
-  Generates handover documents
-  Handles failures gracefully