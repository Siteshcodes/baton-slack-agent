# 🏗️ Architecture — Baton

> Detailed technical architecture for the Baton Slack agent.

---

## System Overview

Baton is a Slack agent that provides institutional memory for volunteer-run organizations. It mines workspace history using the Real-Time Search API and delivers AI-synthesized, receipt-backed answers via Groq's Llama 3.3 70B model.

### Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Honesty First** | Admits "I don't know" when no relevant messages exist |
| **Receipts Always** | Every claim includes a permalink to the original message |
| **Permission-Aware** | Uses Slack's RTS API which respects channel access controls |
| **Graceful Degradation** | Falls back to text summaries when Canvas API fails |
| **Resilient** | Retries on transient errors, recovers from malformed LLM outputs |

---

## Components

### 1. `app.py` — Entry Point

| Aspect | Detail |
|--------|--------|
| **Framework** | Slack Bolt for Python |
| **Connection** | Socket Mode (WebSocket — no public URL needed) |
| **Responsibilities** | Environment validation, logging setup, Assistant middleware registration |
| **Startup Check** | Validates all 4 required env vars or exits with clear error |

### 2. `handlers.py` — Event Router

| Aspect | Detail |
|--------|--------|
| **Middleware** | Bolt `Assistant` class for proper thread lifecycle |
| **Events Handled** | `thread_started`, `thread_context_changed`, `user_message` |
| **Action Token** | Extracted from `payload["assistant_thread"]["action_token"]`, cached per thread |
| **Routing** | Handover requests → `generate_handover_pack()`, questions → `process_question()` |

#### Action Token Flow

```
assistant_thread_started
    → save thread context

user sends message
    → extract action_token from payload["assistant_thread"]
    → cache by (channel, thread_ts)
    → pass to search function
```

### 3. `agent.py` — Core Logic

The agent implements three key functions:

#### `search_workspace(query, client, action_token)`
- **API**: `assistant.search.context` (Real-Time Search)
- **Auth**: Bot token + action_token (minted per-thread by Slack)
- **Returns**: JSON array of messages with text, permalink, channel, user, timestamp
- **Error Handling**: Returns empty results with error message on failure

#### `process_question(question, client, action_token)`
- **LLM**: Groq — Llama 3.3 70B Versatile
- **Pattern**: Tool-calling loop (max 3 rounds)
- **Recovery**: Parses malformed Groq `tool_use_failed` errors and executes search manually

```
Round 1:  User question → LLM → tool_call(search_workspace)
                                      ↓
                               RTS API search
                                      ↓
Round 2:  Search results → LLM → final answer with citations
                                  (or another search round)
```

#### `generate_handover_pack(client, target_user, requesting_user, action_token)`
- **Strategy**: 5 targeted searches (from user, mentions, responsibilities, handover, role)
- **Dedup**: By message timestamp
- **Output**: Slack Canvas with structured sections → shared with requester
- **Fallback**: Plain-text summary with permalinks if Canvas API fails

---

## Data Flow

```
┌─────────────────────────────────────────────────────┐
│                  Slack Workspace                     │
│                                                      │
│  User opens Assistant Thread → Types question        │
└──────────────────┬──────────────────────────────────┘
                   │ Socket Mode (WebSocket)
                   │ Events: assistant_thread_started,
                   │         user_message
                   ↓
┌──────────────────────────────────────────────────────┐
│  app.py  →  handlers.py  →  agent.py                 │
│  (Bolt)     (Assistant       (Search Loop)            │
│              Middleware)                              │
│                                 │                     │
│                   ┌─────────────┼──────────────┐      │
│                   ↓                            ↓      │
│         ┌──────────────────┐      ┌───────────────┐   │
│         │ Slack RTS API    │      │   Groq LLM    │   │
│         │ action_token     │      │  Llama 3.3    │   │
│         │ 20 results/query │      │  Tool Calling │   │
│         └────────┬─────────┘      └───────┬───────┘   │
│                  └─────────────┬──────────┘           │
│                                ↓                      │
│                  Cited Answer + Permalinks             │
│                                ↓                      │
│                  say() → Slack Thread                  │
└──────────────────────────────────────────────────────┘
```

---

## Resilience Features

### Groq Error Recovery

| Error | Strategy |
|-------|----------|
| **429 Rate Limit** | Exponential backoff retry (2 attempts, 1s→2s delay) |
| **500+ Server Error** | Same retry logic |
| **400 `tool_use_failed`** | Parse malformed XML tool call, execute search manually, call LLM without tools |
| **Malformed JSON args** | Fall back to using original question as search query |

### `tool_use_failed` Recovery

Groq's Llama model sometimes generates tool calls in raw XML instead of structured JSON:

```xml
<function=search_workspace{"query": "hello"}</function>
```

The `_parse_failed_tool_call()` function handles 4 observed variants and extracts the query to execute the search manually.

---

## Security & Permissions

### Required Slack Scopes

| Scope | Purpose |
|-------|---------|
| `assistant:write` | Post to assistant threads |
| `chat:write` | Send messages |
| `canvases:write` | Create handover packs |
| `canvases:read` | Read canvas content |
| `channels:history` | Access channel history |
| `channels:read` | List channels |
| `groups:read` | Access private channel metadata |
| `im:history` | Access DM history |
| `im:read` | Read DM metadata |
| `search:read.public` | Search public channels |
| `search:read.files` | Search files |
| `users:read` | Get user information |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_BOT_TOKEN` | ✅ | Bot user OAuth token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | ✅ | App signing secret |
| `SLACK_APP_TOKEN` | ✅ | App-level token for Socket Mode (`xapp-...`) |
| `GROQ_API_KEY` | ✅ | Groq API key (`gsk_...`) |
| `GROQ_MODEL` | ❌ | Model identifier (default: `llama-3.3-70b-versatile`) |

### Security Notes

- Secrets are loaded from `.env` (gitignored) — never committed
- Action tokens are ephemeral, minted per-thread by Slack
- Bot only searches channels it has been added to
- RTS API respects workspace permission boundaries
