import json
import os
from datetime import datetime, timezone
from config import LOG_FILE, LLM_MODEL

_QUESTION_LIMIT = 300
_PREVIEW_LIMIT = 200
_CONSOLE_QUESTION_LIMIT = 60


def log_interaction(question: str, tier: str, response: str) -> None:
    """
    Append a structured record of this interaction to the audit log.

    TODO — Milestone 3:

    Before writing any code, complete specs/auditor-spec.md. The key decisions
    are what fields to log, how much of the question and response to include,
    and how to handle the logs/ directory not existing yet.

    Each record should be a JSON object written as a single line to LOG_FILE
    (defined in config.py as "logs/audit.jsonl").

    Required fields:
      - "timestamp"        : ISO 8601 datetime string
      - "tier"             : the safety tier assigned to this question
      - "question"         : the user's question (truncate to 300 chars if longer)
      - "response_preview" : first 200 characters of the response

    If the logs/ directory doesn't exist, create it before writing.

    Also print a one-line summary to the terminal so you can see logged
    interactions in real time without opening the file:
      e.g. [LOGGED] tier=caution | "How do I replace a faucet?" → 47 chars

    Design your log entry in specs/auditor-spec.md before implementing here.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tier": tier,
        "question": question[:_QUESTION_LIMIT],
        "response_preview": response[:_PREVIEW_LIMIT],
        "model": LLM_MODEL,
        "question_length": len(question),
    }

    # A logging failure must never break the user-facing pipeline.
    try:
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # One JSON object per line — never json.dump(..., indent=), which would
        # pretty-print across multiple lines and break the .jsonl format.
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[LOG ERROR] could not write audit log: {type(exc).__name__}: {exc}")
        return

    short_q = question[:_CONSOLE_QUESTION_LIMIT]
    if len(question) > _CONSOLE_QUESTION_LIMIT:
        short_q += "…"
    print(f'[LOGGED] tier={tier} | "{short_q}" | response {len(response)} chars')
