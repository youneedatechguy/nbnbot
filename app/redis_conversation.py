import json
import logging
from datetime import datetime

import redis
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UserContext(BaseModel):
    user_id: str
    recent_tasks: list[str] = []
    current_project: str | None = None
    message_history: list[dict[str, str]] = []
    last_updated: datetime | None = None


class RedisConversationStore:
    def __init__(self, redis_url: str | None = None, ttl_hours: int = 24):
        self.redis_url = redis_url
        self.ttl_seconds = ttl_hours * 3600
        self._client: redis.Redis | None = None

        if redis_url:
            try:
                self._client = redis.from_url(redis_url)
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")

    def _key(self, user_id: str) -> str:
        return f"conversation:{user_id}"

    def get_context(self, user_id: str) -> UserContext | None:
        if not self._client:
            return None

        try:
            data = self._client.get(self._key(user_id))
            if data:
                return UserContext(**json.loads(data))
        except Exception as e:
            logger.warning(f"Error getting context: {e}")
        return None

    def save_context(self, context: UserContext) -> bool:
        if not self._client:
            return False

        try:
            context.last_updated = datetime.utcnow()
            data = context.model_dump_json()
            self._client.setex(
                self._key(context.user_id),
                self.ttl_seconds,
                data,
            )
            return True
        except Exception as e:
            logger.warning(f"Error saving context: {e}")
            return False

    def add_message(self, user_id: str, role: str, content: str) -> bool:
        context = self.get_context(user_id) or UserContext(user_id=user_id)

        context.message_history.append({"role": role, "content": content})

        if len(context.message_history) > 20:
            context.message_history = context.message_history[-20:]

        return self.save_context(context)

    def add_recent_task(self, user_id: str, task_id: str) -> bool:
        context = self.get_context(user_id) or UserContext(user_id=user_id)

        if task_id not in context.recent_tasks:
            context.recent_tasks.insert(0, task_id)
            context.recent_tasks = context.recent_tasks[:10]

        return self.save_context(context)

    def set_current_project(self, user_id: str, project_id: str) -> bool:
        context = self.get_context(user_id) or UserContext(user_id=user_id)

        context.current_project = project_id

        return self.save_context(context)

    def delete_context(self, user_id: str) -> bool:
        if not self._client:
            return False

        try:
            self._client.delete(self._key(user_id))
            return True
        except Exception as e:
            logger.warning(f"Error deleting context: {e}")
            return False

    @property
    def is_connected(self) -> bool:
        return self._client is not None
