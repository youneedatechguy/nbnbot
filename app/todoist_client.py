from datetime import datetime
from typing import Any
from pydantic import BaseModel
import httpx
import logging
import re

logger = logging.getLogger(__name__)


class TodoistTask(BaseModel):
    id: str
    content: str
    description: str = ""
    project_id: str | None = None
    is_completed: bool = False
    due_string: str | None = None
    due_datetime: str | None = None
    priority: int = 4
    labels: list[str] = []


class TodoistSection(BaseModel):
    id: str
    name: str
    project_id: str


class TodoistProject(BaseModel):
    id: str
    name: str
    color: str | None = None
    is_favorite: bool = False


class TodoistClient:
    BASE_URL = "https://api.todoist.com/rest/v2"
    
    def __init__(self, api_token: str, mock_mode: bool = False):
        self.api_token = api_token
        self.mock_mode = mock_mode or not api_token
        self._mock_tasks: dict[str, TodoistTask] = {}
        self._mock_counter = 0
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        json: dict | None = None,
    ) -> dict | list | None:
        if self.mock_mode:
            return self._handle_mock(method, endpoint, json)
        
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                json=json,
                headers=headers,
            )
            response.raise_for_status()
            return response.json() if response.text else None
    
    def _handle_mock(
        self,
        method: str,
        endpoint: str,
        json: dict | None = None,
    ) -> dict | list | None:
        self._mock_counter += 1
        task_id = f"mock_{self._mock_counter}"
        
        if method == "GET" and endpoint == "/tasks":
            return [task.model_dump() for task in self._mock_tasks.values()]
        
        if method == "GET" and endpoint.startswith("/tasks/"):
            task_id = endpoint.split("/")[-1]
            if task_id in self._mock_tasks:
                return self._mock_tasks[task_id].model_dump()
            return None
        
        if method == "POST" and endpoint == "/tasks":
            task = TodoistTask(
                id=task_id,
                content=json.get("content", "") if json else "",
                description=json.get("description", "") if json else "",
                project_id=json.get("project_id") if json else None,
                priority=json.get("priority", 4) if json else 4,
            )
            self._mock_tasks[task_id] = task
            return task.model_dump()
        
        if method == "PATCH" and endpoint.startswith("/tasks/"):
            task_id = endpoint.split("/")[-1]
            if task_id in self._mock_tasks:
                task = self._mock_tasks[task_id]
                for key, value in (json or {}).items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                return task.model_dump()
            return None
        
        if method == "DELETE" or (method == "POST" and "/close" in endpoint):
            match = re.match(r"^/tasks/([^/]+)", endpoint)
            task_id = match.group(1) if match else task_id
            if task_id in self._mock_tasks:
                if method == "POST" and "/close" in endpoint:
                    self._mock_tasks[task_id].is_completed = True
                    return self._mock_tasks[task_id].model_dump()
                del self._mock_tasks[task_id]
            return True
        
        return None
    
    async def get_tasks(self, project_id: str | None = None) -> list[TodoistTask]:
        endpoint = "/tasks"
        if project_id:
            endpoint += f"?project_id={project_id}"
        
        result = await self._request("GET", endpoint, None)
        if isinstance(result, list):
            return [TodoistTask(**task) for task in result]
        return []
    
    async def get_task(self, task_id: str) -> TodoistTask | None:
        result = await self._request("GET", f"/tasks/{task_id}", None)
        if result:
            return TodoistTask(**result)
        return None
    
    async def create_task(
        self,
        content: str,
        project_id: str | None = None,
        description: str = "",
        due_string: str | None = None,
        priority: int = 4,
    ) -> TodoistTask:
        json = {
            "content": content,
            "description": description,
            "priority": priority,
        }
        if project_id:
            json["project_id"] = project_id
        if due_string:
            json["due_string"] = due_string
        
        result = await self._request("POST", "/tasks", json)
        return TodoistTask(**result)
    
    async def update_task(
        self,
        task_id: str,
        content: str | None = None,
        description: str | None = None,
        is_completed: bool | None = None,
    ) -> TodoistTask | None:
        json = {}
        if content is not None:
            json["content"] = content
        if description is not None:
            json["description"] = description
        if is_completed is not None:
            json["is_completed"] = is_completed
        
        result = await self._request("PATCH", f"/tasks/{task_id}", json)
        if result:
            return TodoistTask(**result)
        return None
    
    async def complete_task(self, task_id: str) -> bool:
        result = await self._request(
            "POST",
            f"/tasks/{task_id}/close",
            None,
        )
        return result is not None
    
    async def delete_task(self, task_id: str) -> bool:
        await self._request("DELETE", f"/tasks/{task_id}", None)
        return True
    
    async def get_projects(self) -> list[TodoistProject]:
        result = await self._request("GET", "/projects", None)
        if isinstance(result, list):
            return [TodoistProject(**proj) for proj in result]
        return []
    
    async def get_sections(self, project_id: str) -> list[TodoistSection]:
        result = await self._request("GET", f"/sections?project_id={project_id}", None)
        if isinstance(result, list):
            return [TodoistSection(**sec) for sec in result]
        return []