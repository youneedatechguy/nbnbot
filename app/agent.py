import json
import logging
from pydantic import BaseModel
from openai import AsyncOpenAI
from .todoist_client import TodoistClient, TodoistTask

logger = logging.getLogger(__name__)


class Intent(BaseModel):
    action: str
    target: str | None = None
    parameters: dict = {}


class IntentClassifier:
    SYSTEM_PROMPT = """You are a Todoist task assistant. Parse user messages into structured intents.
    
Supported actions:
- create_task: Create a new task (requires: content)
- list_tasks: List existing tasks (optional: project)
- complete_task: Mark a task as complete (requires: task_name)
- help: Show help message

Respond with JSON only:
{"action": "create_task", "content": "...", "project": "..."}
{"action": "list_tasks", "project": "..."}
{"action": "complete_task", "task_name": "..."}
{"action": "help"}
"""


class TodoistAgent:
    def __init__(
        self,
        todoist_client: TodoistClient,
        openai_api_key: str | None = None,
        model_name: str = "gpt-4o-mini",
    ):
        self.todoist_client = todoist_client
        self.openai_api_key = openai_api_key
        self.model_name = model_name
        self.client = AsyncOpenAI(api_key=openai_api_key) if openai_api_key else None
    
    async def process_message(self, message: str, from_number: str) -> str:
        if not self.client:
            return self._fallback_process(message)
        
        try:
            intent = await self._classify_intent(message)
            return await self._execute_intent(intent, message)
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return self._fallback_process(message)
    
    async def _classify_intent(self, message: str) -> dict:
        if not self.client:
            return self._simple_classify(message)
        
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": IntentClassifier.SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            response_format={"type": "json_object"},
        )
        
        return json.loads(response.choices[0].message.content)
    
    def _simple_classify(self, message: str) -> dict:
        text = message.lower()
        
        if "complete" in text or "done" in text or "finished" in text:
            return {"action": "complete_task", "task_name": message}
        if "list" in text or "show" in text or "my tasks" in text:
            return {"action": "list_tasks"}
        if "create" in text or "add" in text or "new task" in text:
            return {"action": "create_task", "content": message}
        
        return {"action": "help"}
    
    async def _execute_intent(self, intent: dict, original_message: str) -> str:
        action = intent.get("action", "help")
        
        if action == "create_task":
            content = intent.get("content", original_message)
            project = intent.get("project")
            due = intent.get("due")
            
            task = await self.todoist_client.create_task(
                content=content,
                project_id=project,
                due_string=due,
            )
            return f"✅ Task created: {task.content}\nID: {task.id}"
        
        if action == "list_tasks":
            project = intent.get("project")
            tasks = await self.todoist_client.get_tasks(project)
            
            if not tasks:
                return "No tasks found."
            
            lines = ["📋 *Your Tasks:*\n"]
            for i, task in enumerate(tasks[:10], 1):
                status = "✓" if task.is_completed else "○"
                lines.append(f"{status} {i}. {task.content}")
            
            return "\n".join(lines)
        
        if action == "complete_task":
            task_name = intent.get("task_name", original_message)
            tasks = await self.todoist_client.get_tasks()
            
            for task in tasks:
                if task_name.lower() in task.content.lower():
                    await self.todoist_client.complete_task(task.id)
                    return f"✓ Completed: {task.content}"
            
            return f"Task not found: {task_name}"
        
        return self._help_message()
    
    def _fallback_process(self, message: str) -> str:
        intent = self._simple_classify(message)
        return self._help_message()
    
    def _help_message(self) -> str:
        return (
            "📝 *Commands:*\n"
            "• Create task: \"Create a task to...\"\n"
            "• List tasks: \"Show my tasks\"\n"
            "• Complete task: \"Complete [task name]\""
        )