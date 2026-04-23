"""Quick integration test for WhatsApp-Todoist bot"""
import asyncio
from app.todoist_client import TodoistClient
from app.agent import TodoistAgent
from app.config import settings


async def test_agent():
    print("Testing WhatsApp-Todoist Integration...")

    # Initialize client (will use mock if no token)
    client = TodoistClient(settings.todoist_api_token)

    # Initialize agent
    agent = TodoistAgent(
        todoist_client=client,
        openai_api_key=settings.openai_api_key,
        openrouter_api_key=settings.openrouter_api_key,
        model_provider=settings.model_provider or "openai",
        model_name=settings.model_name or "gpt-4o-mini",
    )

    # Test messages
    test_messages = [
        "help",
        "Create a task to test the integration",
        "List my tasks",
    ]

    for msg in test_messages:
        print(f"\n📱 User: {msg}")
        response = await agent.process_message(msg, "whatsapp:+1234567890")
        print(f"🤖 Bot: {response}")

    print("\n✅ Integration test complete!")


if __name__ == "__main__":
    asyncio.run(test_agent())
