import asyncio
import logging
import os
from typing import Any

from pyaileys import WhatsAppClient

from .agent import TodoistAgent
from .config import settings
from .todoist_client import TodoistClient

logger = logging.getLogger(__name__)


class WhatsAppHandler:
    def __init__(
        self,
        todoist_client: TodoistClient,
        agent: TodoistAgent,
        session_path: str = "./auth",
    ):
        self.todoist_client = todoist_client
        self.agent = agent
        self.session_path = session_path
        self.client: WhatsAppClient | None = None
        self.auth_state = None
        self._connected = False

    @classmethod
    async def create(
        cls,
        todoist_client: TodoistClient,
        agent: TodoistAgent,
        session_path: str | None = None,
    ) -> "WhatsAppHandler":
        handler = cls(
            todoist_client=todoist_client,
            agent=agent,
            session_path=session_path or settings.whatsapp_session_path or "./auth",
        )
        await handler._connect()
        return handler

    async def _connect(self) -> None:
        auth_path = self.session_path
        os.makedirs(auth_path, exist_ok=True)

        try:
            self.client, self.auth_state = await WhatsAppClient.from_auth_folder(auth_path)
        except FileNotFoundError:
            logger.info("No existing session found, creating new auth folder")
            self.client, self.auth_state = await WhatsAppClient.from_auth_folder(auth_path)

        self.client.on("messages.upsert", self._on_message)
        await self.client.connect()
        logger.info("WhatsApp connected successfully")

    async def _on_message(self, data: dict[str, Any]) -> None:
        try:
            messages = data.get("messages", [])
            for message in messages:
                if message.get("key", {}).get("fromMe"):
                    continue

                jid = message["key"]["remoteJid"]
                msg_body = self._extract_message_text(message)

                if not msg_body:
                    continue

                logger.info(f"Received message from {jid}: {msg_body}")

                try:
                    response = await self.agent.process_message(msg_body, jid)
                    await self._send_response(jid, response)
                except Exception as e:
                    logger.exception(f"Error processing message: {e}")
                    await self._send_response(jid, "Sorry, an error occurred. Please try again.")

        except Exception as e:
            logger.exception(f"Error handling message: {e}")

    def _extract_message_text(self, message: dict) -> str | None:
        msg = message.get("message", {})
        
        if conversation := msg.get("conversation"):
            return conversation.strip()
        
        if ext_text := msg.get("extendedTextMessage", {}):
            return ext_text.get("text", "").strip()
        
        return None

    async def _send_response(self, jid: str, text: str) -> None:
        if not self.client:
            logger.warning("Client not connected, cannot send message")
            return

        try:
            await self.client.send_message(jid, text)
            logger.info(f"Sent message to {jid}")
        except Exception as e:
            logger.exception(f"Error sending message to {jid}: {e}")

    async def disconnect(self) -> None:
        if self.client:
            await self.client.disconnect()
            logger.info("WhatsApp disconnected")

    @property
    def is_connected(self) -> bool:
        return self.client is not None