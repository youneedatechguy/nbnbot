from .todoist_client import TodoistClient
from .agent import TodoistAgent
import logging

logger = logging.getLogger(__name__)


class TwilioHandler:
    def __init__(self, todoist_client: TodoistClient):
        self.todoist_client = todoist_client
        self.agent: TodoistAgent | None = None
    
    def set_agent(self, agent: TodoistAgent):
        self.agent = agent
    
    async def process_message(self, message: str, from_number: str) -> str:
        logger.info(f"Processing message from {from_number}: {message}")
        
        text = message.strip().lower()
        
        if text in ["help", "/help", "?"]:
            return (
                "📝 *Todoist Bot Commands*\n\n"
                "• Create task: \"Create a task to buy milk\"\n"
                "• List tasks: \"List my tasks\" or \"Show tasks\"\n"
                "• Complete task: \"Complete [task name]\"\n"
                "• Help: Send this message\n"
            )
        
        if self.agent:
            response = await self.agent.process_message(message, from_number)
            return response
        
        return (
            "I can help you manage Todoist tasks!\n"
            "Send me a command like:\n"
            "• \"Create a task to buy milk tomorrow\"\n"
            "• \"Show my tasks\"\n"
        )
    
    def parse_incoming_message(self, data: dict) -> tuple[str, str]:
        body = data.get("Body", "").strip()
        from_num = data.get("From", "")
        return body, from_num