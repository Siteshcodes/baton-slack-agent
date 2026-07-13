import json
import logging
import os
import re
import time
from typing import Any, Dict, List

from groq import Groq
from slack_sdk import WebClient

logger = logging.getLogger(__name__)

# Configuration
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_TOOL_ROUNDS = 3        
GROQ_MAX_RETRIES = 2         
GROQ_RETRY_BASE_DELAY = 1.0 

# Module-level Groq client — reused across calls.
_groq_client: Groq | None = None


def _get_groq_client() -> Groq:
    """Lazily create and cache the Groq client."""
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq()
    return _groq_client


# Tool definitions exposed to the LLM

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_workspace",
            "description": (
                "Search the Slack workspace history for messages relevant "
                "to a question. Use this for ALL questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language search query",
                    },
                },
                "required": ["query"],
            },
        },
    }
]

SYSTEM_PROMPT = """\
You are Baton, an institutional memory assistant for a volunteer-run organization. \
Your role is to answer questions about the organization's history, decisions, \
contacts, and procedures using ONLY information from the Slack workspace.

CRITICAL RULES:
1. Use the search_workspace tool for EVERY question. Do not answer from general knowledge.
2. Cite the permalink for every claim you make. Format citations as [source](permalink).
3. If the search returns no relevant information, honestly say \
"I don't have information about that in the workspace history."
4. Be concise and direct. Focus on the facts found in the messages.
5. When multiple messages are relevant, synthesize them into a coherent answer.
6. Preserve the exact wording from the original messages when quoting specific details.
7. Format your answer using Slack mrkdwn: *bold* for key facts, bullet lists for multiple items.

Your goal is to help volunteers understand what happened in the past, with receipts \
to prove it."""

# Groq call with retry

def _groq_chat(messages: list, tools: list | None = None) -> Any:
    """Call Groq chat completions with exponential-backoff retry.

    Retries on rate-limit (429) and transient server errors (>=500).
    Raises on persistent or client errors.
    """
    client = _get_groq_client()
    last_err: Exception | None = None

    for attempt in range(GROQ_MAX_RETRIES + 1):
        try:
            kwargs: dict = {"model": MODEL, "messages": messages}
            if tools:
                kwargs["tools"] = tools
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            last_err = exc
            # Retry only on rate-limit or server errors
            status = getattr(exc, "status_code", None)
            if status and (status == 429 or status >= 500) and attempt < GROQ_MAX_RETRIES:
                delay = GROQ_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "Groq API error (attempt %d/%d, status %s), retrying in %.1fs: %s",
                    attempt + 1, GROQ_MAX_RETRIES + 1, status, delay, exc,
                )
                time.sleep(delay)
                continue
            raise 

 
    raise last_err  


def _parse_failed_tool_call(exc: Exception) -> dict | None:
    """Extract function name and args from Groq's tool_use_failed error.

    When Llama models emit tool calls in raw XML format instead of
    structured JSON, Groq returns a 400 with the malformed generation
    in the error body.  Observed formats include:

        <function=search_workspace {"query": "hello"} </function>
        <function=search_workspace,{"query": "hello"}</function>
        <function=search_workspace{"query": "hello"}</function>
        <function=search_workspace [{"query": "hello"}]</function>

    This helper parses all variants so we can execute the search manually.
    """
    body = getattr(exc, "body", None) or {}
    err_info = body.get("error", {}) if isinstance(body, dict) else {}
    code = err_info.get("code", "")
    if code != "tool_use_failed":
        return None

    failed_gen = err_info.get("failed_generation", "")
    if not failed_gen:
        return None

    # Flexible pattern: <function=name + optional separators + first {...}
    match = re.search(r"<function=(\w+)[,\s\[]*(\{[^}]*\})", failed_gen)
    if not match:
        return None

    func_name = match.group(1)
    try:
        args = json.loads(match.group(2))
    except (json.JSONDecodeError, TypeError):
        return None

    logger.info("Recovered tool call from failed_generation: %s(%s)", func_name, args)
    return {"name": func_name, "arguments": args}


# Real-Time Search

def search_workspace(query: str, client: WebClient, action_token: str | None = None) -> str:
    """Search the workspace using the Real-Time Search API.

    Returns a JSON string with a ``messages`` array.  On error, the array
    is empty and an ``error`` key is present.
    """
    if not query or not query.strip():
        return json.dumps({"messages": [], "error": "Empty search query"})

    try:
        payload: dict[str, Any] = {
            "query": query.strip(),
            "channel_types": ["public_channel", "private_channel"],
            "content_types": ["messages"],
            "limit": 20,
        }

        if action_token:
            payload["action_token"] = action_token

        resp = client.api_call("assistant.search.context", json=payload)
        data = resp.data
        messages = (data.get("results") or {}).get("messages", [])

        if not messages:
            return json.dumps({"messages": []})

        formatted: list[dict] = []
        for msg in messages:
            formatted.append({
                "text": msg.get("text", msg.get("content", "")),
                "permalink": msg.get("permalink", ""),
                "channel": msg.get("channel_id", ""),
                "user": msg.get("user", ""),
                "timestamp": msg.get("timestamp", ""),
            })

        return json.dumps({"messages": formatted})

    except Exception as exc:
        logger.error("Search error for query %r: %s", query, exc)
        return json.dumps({"messages": [], "error": str(exc)})


# Question processing — tool-calling loop

def process_question(question: str, client: WebClient, action_token: str | None = None) -> str:
    """Process a user question through the search + reasoning loop.

    Supports multiple rounds of tool calls (up to MAX_TOOL_ROUNDS) and
    handles parallel tool calls within a single response.
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for round_num in range(MAX_TOOL_ROUNDS):
        try:
            response = _groq_chat(messages, tools=TOOLS)
        except Exception as exc:
            # Handle Groq tool_use_failed (malformed tool call) 
            parsed = _parse_failed_tool_call(exc)
            if parsed and parsed["name"] == "search_workspace":
                query = parsed["arguments"].get("query", question)
                logger.info("Recovered search from failed tool call — query: %r", query)
                search_result = search_workspace(query, client, action_token)

                # Feed search results back and ask model to answer WITHOUT tools.
                messages.append({
                    "role": "assistant",
                    "content": f"I searched the workspace for: {query}",
                })
                messages.append({
                    "role": "user",
                    "content": (
                        f"Here are the search results:\n\n{search_result}\n\n"
                        "Please answer the original question based on these results. "
                        "Cite the permalink for every claim."
                    ),
                })
                try:
                    fallback = _groq_chat(messages, tools=None)
                    return fallback.choices[0].message.content or "I couldn't find a clear answer."
                except Exception as inner:
                    logger.error("Fallback Groq call also failed: %s", inner)

            logger.error("Groq API call failed: %s", exc)
            return (
                "I'm having trouble connecting to my reasoning engine right now. "
                "Please try again in a moment."
            )

        choice = response.choices[0].message

        # No tool calls — the model is done; return its answer.
        if not choice.tool_calls:
            return choice.content or "I couldn't process that question."

        # Append the assistant message (with tool_calls) to history.
        messages.append(choice)

        # Execute every tool call the model requested.
        for tc in choice.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Malformed tool arguments from LLM: %s", tc.function.arguments)
                args = {"query": question}

            search_query = args.get("query", question)
            logger.info("Search round %d — query: %r", round_num + 1, search_query)
            result = search_workspace(search_query, client, action_token)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # If we exhausted the loop without a final text answer, do one last
    # call WITHOUT tools to force the model to synthesize.
    try:
        final = _groq_chat(messages, tools=None)
        return final.choices[0].message.content or "I couldn't find a clear answer."
    except Exception as exc:
        logger.error("Final Groq synthesis call failed: %s", exc)
        return (
            "I found some search results but had trouble putting together "
            "an answer. Please try rephrasing your question."
        )


# Handover pack generation

def generate_handover_pack(
    client: WebClient,
    target_user: str,
    requesting_user: str,
    action_token: str | None = None,
) -> str:
    """Generate a handover pack canvas for a user.

    Searches for all messages involving the target user and organises them
    into a structured Slack Canvas document.  Falls back to a plain-text
    summary if Canvas creation fails.
    """
    # Resolve display name
    try:
        user_info = client.users_info(user=target_user)
        user_name = user_info["user"].get("real_name") or user_info["user"].get("name", target_user)
    except Exception as exc:
        logger.warning("Could not resolve user %s: %s", target_user, exc)
        user_name = target_user

    # Multi-query search strategy
    search_queries = [
        f"from:{target_user}",
        f"mentions:{target_user}",
        f"responsibilities of {user_name}",
        f"{user_name} is responsible for",
        f"handover {user_name}",
    ]

    all_messages: list[dict] = []
    for query in search_queries:
        try:
            payload: dict[str, Any] = {
                "query": query,
                "channel_types": ["public_channel", "private_channel"],
                "content_types": ["messages"],
                "limit": 50,
            }
            if action_token:
                payload["action_token"] = action_token

            resp = client.api_call("assistant.search.context", json=payload)
            results = (resp.data.get("results") or {}).get("messages", [])
            all_messages.extend(results)
        except Exception as exc:
            logger.error("Search error for handover query %r: %s", query, exc)

    # Deduplicate by timestamp
    seen: set[str] = set()
    unique_messages: list[dict] = []
    for msg in all_messages:
        ts = msg.get("timestamp", "")
        if ts and ts not in seen:
            seen.add(ts)
            unique_messages.append(msg)

    if not unique_messages:
        return f"No messages found for {user_name} in the workspace history."

    # Attempt Canvas creation 
    try:
        blocks: list[dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Handover Pack: {user_name}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"This document contains institutional knowledge and "
                        f"responsibilities for {user_name}, extracted from the "
                        f"workspace history."
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Key Messages ({len(unique_messages)} found)",
                },
            },
        ]

        for msg in unique_messages[:50]:
            text = (msg.get("text") or msg.get("content") or "")[:500]
            permalink = msg.get("permalink", "")
            channel = msg.get("channel_id", "")

            blocks.extend([
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{text}*\n_Channel: {channel}_",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"<{permalink}|View original message>" if permalink else "_No permalink available_",
                    },
                },
                {"type": "divider"},
            ])

        canvas_resp = client.api_call("canvases.create", json={
            "document_title": f"Handover Pack: {user_name}",
            "document_content": {"type": "canvas", "blocks": blocks},
        })
        canvas_id = canvas_resp.data.get("canvas", {}).get("id")

        if not canvas_id:
            raise ValueError("Canvas API returned no canvas ID")

        # Share with the requesting user
        client.api_call("canvases.share", json={
            "canvas_id": canvas_id,
            "user_ids": [requesting_user],
        })

        return f"https://slack.com/canvas/{canvas_id}"

    except Exception as exc:
        logger.error("Canvas creation failed, falling back to text summary: %s", exc)
        lines = [
            f"*Handover Pack for {user_name}*\n",
            f"Found {len(unique_messages)} relevant messages:\n",
        ]
        for i, msg in enumerate(unique_messages[:20], 1):
            text = (msg.get("text") or msg.get("content") or "")[:200]
            permalink = msg.get("permalink", "")
            lines.append(f"{i}. {text}")
            if permalink:
                lines.append(f"   <{permalink}|View original>\n")
            else:
                lines.append("")

        return "\n".join(lines)
