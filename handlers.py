import logging
import re
from typing import Any

from slack_bolt import Assistant
from slack_sdk import WebClient

from agent import generate_handover_pack, process_question

logger = logging.getLogger(__name__)

# Cache action_tokens by (channel, thread_ts) so they persist across
_action_tokens: dict[tuple[str, str], str] = {}

# Suggested prompts shown when a user opens the assistant thread.
SUGGESTED_PROMPTS = [
    {
        "title": "How did we run last year's rapid tournament?",
        "message": "How did we run last year's rapid tournament?",
    },
    {
        "title": "Who is our arbiter contact?",
        "message": "Who is our arbiter contact and how do we book them?",
    },
    {
        "title": "Generate a handover pack",
        "message": "Generate a handover pack for our outgoing secretary.",
    },
]


def _extract_action_token(payload: dict, channel: str, thread_ts: str) -> str | None:
    """Extract action_token from the payload and cache it per thread.

    The action_token lives inside payload["assistant_thread"]["action_token"].
    We cache it so that if a subsequent message in the same thread
    doesn't include it, we can still use the previously seen value.
    """
    at_data = payload.get("assistant_thread", {})
    token = at_data.get("action_token")

    if token:
        _action_tokens[(channel, thread_ts)] = token
    else:
        # Fall back to cached token for this thread
        token = _action_tokens.get((channel, thread_ts))

    return token


def build_assistant() -> Assistant:
    """Build and return the configured Assistant middleware."""
    assistant = Assistant()

    # Thread started — greet user and set up prompts
    @assistant.thread_started
    def handle_thread_started(
        say, set_suggested_prompts, save_thread_context, payload, logger
    ):
        # Save the thread context (channel, team) for later retrieval.
        thread_context = payload.get("assistant_thread", {}).get("context", {})
        logger.info("Assistant thread started, context: %s", thread_context)
        save_thread_context(thread_context)

        set_suggested_prompts(prompts=SUGGESTED_PROMPTS)
        say(
            ":wave: Hi! I'm *Baton* — your organization's institutional memory.\n\n"
            "Ask me anything about past decisions, contacts, or how events were run. "
            "Every answer comes with links to the original messages.\n\n"
            "I can also generate a *handover pack* for an outgoing volunteer — "
            "just say `generate handover pack for @user`."
        )

    # Thread context changed — update stored context
    @assistant.thread_context_changed
    def handle_context_changed(save_thread_context, payload, logger):
        thread_context = payload.get("assistant_thread", {}).get("context", {})
        logger.info("Thread context changed: %s", thread_context)
        save_thread_context(thread_context)

    # User message — route to question answering or handover pack
    @assistant.user_message
    def handle_user_message(client, say, set_status, payload, context, body, logger):
        text = (payload.get("text") or "").strip()
        if not text:
            return

        user_id = payload.get("user")
        channel = payload.get("channel", "")
        thread_ts = payload.get("thread_ts", "")

        # Extract and cache the action_token
        action_token = _extract_action_token(payload, channel, thread_ts)
        logger.info(
            "Message from %s: %s… (action_token=%s)",
            user_id, text[:50], bool(action_token),
        )

        # Route: handover pack
        if "handover pack" in text.lower():
            _handle_handover(
                client, say, set_status, text, user_id, action_token
            )
            return

        # Route: regular question
        _handle_question(client, say, set_status, text, action_token)

    return assistant


# Internal route handlers
def _handle_handover(
    client: WebClient,
    say,
    set_status,
    text: str,
    user_id: str,
    action_token: str | None,
) -> None:
    """Generate and deliver a handover pack."""
    set_status("Generating handover pack…")

    # Extract mentioned user, default to the requester.
    target_user = user_id
    mention = re.search(r"<@(\w+)>", text)
    if mention:
        target_user = mention.group(1)

    try:
        result = generate_handover_pack(client, target_user, user_id, action_token)
        say(f":clipboard: Handover pack generated!\n\n{result}")
    except Exception as exc:
        logger.error("Handover pack failed: %s", exc)
        say(
            ":warning: Sorry, I ran into an issue generating the handover pack. "
            "Please try again shortly."
        )


def _handle_question(
    client: WebClient,
    say,
    set_status,
    text: str,
    action_token: str | None,
) -> None:
    """Search the workspace and answer a question."""
    set_status("Searching workspace history…")

    try:
        answer = process_question(text, client, action_token)
        say(answer)
    except Exception as exc:
        logger.error("Question processing failed: %s", exc)
        say(
            ":warning: Sorry, I had trouble finding an answer. "
            "Please try rephrasing your question or try again in a moment."
        )
