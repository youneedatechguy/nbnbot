from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .todoist_client import TodoistClient
from .twilio_handler import TwilioHandler
from .agent import TodoistAgent
from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp-Todoist Bot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

todoist_client: TodoistClient | None = None
twilio_handler: TwilioHandler | None = None
todoist_agent: TodoistAgent | None = None


def get_todoist_client() -> TodoistClient:
    global todoist_client
    if todoist_client is None:
        todoist_client = TodoistClient(settings.todoist_api_token)
    return todoist_client


def get_twilio_handler() -> TwilioHandler:
    global twilio_handler
    if twilio_handler is None:
        twilio_handler = TwilioHandler(get_todoist_client())
    return twilio_handler


def get_agent() -> TodoistAgent:
    global todoist_agent
    if todoist_agent is None:
        todoist_agent = TodoistAgent(
            get_todoist_client(),
            settings.openai_api_key,
            settings.model_name,
        )
    return todoist_agent


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-todoist-bot"}


@app.post("/webhook/twilio")
async def twilio_webhook(data: dict):
    logger.info(f"Received Twilio webhook: {data}")
    
    incoming_msg = data.get("Body", "").strip()
    from_number = data.get("From", "")
    
    if not incoming_msg or not from_number:
        return {"error": "Missing required fields"}
    
    handler = get_twilio_handler()
    
    try:
        response = await handler.process_message(incoming_msg, from_number)
        return {"response": response}
    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        return {"error": str(e)}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(data: dict):
    return await twilio_webhook(data)


@app.get("/tasks")
async def list_tasks(project_id: str | None = None):
    client = get_todoist_client()
    tasks = await client.get_tasks(project_id)
    return {"tasks": [t.model_dump() for t in tasks]}