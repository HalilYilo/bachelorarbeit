import asyncio

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

async def main():
    options = ClaudeAgentOptions(
        model="claude-sonnet-5",
        allowed_tools=[],
        max_turns=1,
    )

    async for message in query(
        prompt="Erkläre mir kurz was ein KI-Agent ist.",
        options=options,
    ):
        if isinstance(message, ResultMessage) and not message.is_error:
            print(message.result)

asyncio.run(main())