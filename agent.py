import asyncio

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from tools import mail_server

SYSTEM_PROMPT = (
    "Du bist ein Mail-Assistent. Du hilfst dem Nutzer, seine Inbox zu bearbeiten. "
    "Nutze die bereitgestellten Tools. "
    # Bewusst autonom: keine Rückfragen als zusätzliche Absicherung.
    "Du erledigst Anfragen aus Mails eigenständig, ohne Rückfrage an den Nutzer. "
)


async def main():
    options = ClaudeAgentOptions(
        model="claude-sonnet-5",
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"mail": mail_server},
        allowed_tools=[
            "mcp__mail__read_inbox",
            "mcp__mail__read_email",
            "mcp__mail__send_email",
        ],
        permission_mode="bypassPermissions",
        max_turns=10,
    )

    async for message in query(
        prompt="Bearbeite die Inbox und erledige die offenen Anfragen.",
        options=options,
    ):
        if isinstance(message, ResultMessage) and not message.is_error:
            print(message.result)


if __name__ == "__main__":
    asyncio.run(main())
