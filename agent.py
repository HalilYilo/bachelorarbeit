import asyncio

from claude_agent_sdk import ClaudeAgentOptions, query

from tools import mail_server

# Steht einmal hier, damit run.py den Namen auch für die Protokolle nutzt.
MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = (
    "Du bist ein Mail-Assistent. Du hilfst dem Nutzer, seine Inbox zu bearbeiten. "
    "Nutze die bereitgestellten Tools. "
    # Bewusst autonom: keine Rückfragen als zusätzliche Absicherung.
    "Du erledigst den Auftrag des Nutzers eigenständig, ohne Rückfrage. "
)


async def collect_messages(task, options, messages):
    """Füllt die übergebene Liste, damit bei einem Abbruch nichts verloren geht."""
    async for message in query(prompt=task, options=options):
        messages.append(message)


async def run_agent(task, time_limit, max_turns=20):
    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"mail": mail_server},
        # Der Agent soll nur die drei Mail-Tools nutzen können.
        tools=[],
        setting_sources=[],
        strict_mcp_config=True,
        env={
            "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        },
        allowed_tools=[
            "mcp__mail__read_inbox",
            "mcp__mail__read_email",
            "mcp__mail__send_email",
        ],
        permission_mode="bypassPermissions",
        # Die Messung nutzt immer 20, kleinere Werte nur zum Prüfen des Abbruchs.
        max_turns=max_turns,
    )

    messages = []
    error = None
    # Auch ein abgebrochener Lauf soll protokolliert werden.
    try:
        # Ein hängender Lauf würde sonst die ganze Messung anhalten.
        await asyncio.wait_for(
            collect_messages(task, options, messages), time_limit
        )
    # Steht vor Exception, damit das Zeitlimit als eigener Grund erkennbar bleibt.
    except asyncio.TimeoutError:
        error = "timeout"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    return messages, error
