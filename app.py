import logging
import os
import sys

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

# Centralized logging configuration — only call basicConfig once, here.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# Startup validation
REQUIRED_ENV = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "SLACK_APP_TOKEN", "GROQ_API_KEY"]

_missing = [v for v in REQUIRED_ENV if not os.environ.get(v, "").strip()]
if _missing:
    logger.critical("Missing required environment variables: %s", ", ".join(_missing))
    sys.exit(1)

# Initialize Bolt app with Assistant middleware
from handlers import build_assistant

app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
)

# Register the Assistant — this handles assistant_thread_started,
# assistant_thread_context_changed, and user messages automatically.
app.use(build_assistant())


if __name__ == "__main__":
    logger.info("Starting Baton in Socket Mode…")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
