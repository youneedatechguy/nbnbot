from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import logging
from .todoist_client import TodoistClient
from .agent import TodoistAgent
from .config import settings
from .whatsapp_handler import WhatsAppHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

whatsapp_handler: WhatsAppHandler | None = None
todoist_client: TodoistClient | None = None
todoist_agent: TodoistAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global whatsapp_handler, todoist_client, todoist_agent
    
    logger.info("Starting WhatsApp-Todoist Bot...")
    
    todoist_client = TodoistClient(settings.todoist_api_token)
    todoist_agent = TodoistAgent(
        todoist_client,
        settings.openai_api_key,
        settings.openrouter_api_key,
        settings.model_provider,
        settings.model_name,
    )
    
    try:
        whatsapp_handler = await WhatsAppHandler.create(
            todoist_client=todoist_client,
            agent=todoist_agent,
            session_path=settings.whatsapp_session_path,
        )
        logger.info("WhatsApp handler initialized")
    except Exception as e:
        logger.warning(f"Could not connect to WhatsApp: {e}")
        logger.info("Bot will run in API-only mode without WhatsApp connection")
    
    yield
    
    if whatsapp_handler:
        await whatsapp_handler.disconnect()


app = FastAPI(
    title="WhatsApp-Todoist Bot",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "whatsapp-todoist-bot",
        "whatsapp_connected": whatsapp_handler.is_connected if whatsapp_handler else False,
    }


@app.get("/tasks")
async def list_tasks(project_id: str | None = None):
    if not todoist_client:
        raise HTTPException(status_code=503, detail="Todoist client not initialized")
    
    tasks = await todoist_client.get_tasks(project_id)
    return {"tasks": [t.model_dump() for t in tasks]}