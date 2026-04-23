from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
import logging
from .todoist_client import TodoistClient
from .twilio_handler import TwilioHandler
from .agent import TodoistAgent
from .config import settings
from twilio.request_validator import RequestValidator

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
        # Wire up the agent to the handler
        twilio_handler.set_agent(get_agent())
    return twilio_handler


def get_agent() -> TodoistAgent:
    global todoist_agent
    if todoist_agent is None:
        todoist_agent = TodoistAgent(
            get_todoist_client(),
            settings.openai_api_key,
            settings.openrouter_api_key,
            settings.model_provider,
            settings.model_name,
        )
    return todoist_agent


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-todoist-bot"}


def validate_twilio_request(request: Request, form_data: dict) -> bool:
    """Validate that the request actually came from Twilio"""
    if not settings.twilio_auth_token:
        logger.warning("Twilio auth token not configured - skipping signature validation")
        return True

    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)

    return validator.validate(url, form_data, signature)


@app.post("/webhook/whatsapp", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    MessageSid: str = Form(None),
):
    """Twilio WhatsApp webhook endpoint with signature validation"""
    form_data = {
        "Body": Body,
        "From": From,
        "MessageSid": MessageSid,
    }

    # Validate request is from Twilio
    if not validate_twilio_request(request, form_data):
        logger.warning(f"Invalid Twilio signature from {From}")
        raise HTTPException(status_code=403, detail="Invalid signature")

    logger.info(f"Received WhatsApp message from {From}: {Body}")

    handler = get_twilio_handler()

    try:
        response = await handler.process_message(Body, From)
        # Return TwiML response
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{response}</Message></Response>'
    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>Sorry, an error occurred. Please try again.</Message></Response>'


@app.post("/webhook/twilio", response_class=PlainTextResponse)
async def twilio_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    MessageSid: str = Form(None),
):
    """Twilio SMS/WhatsApp webhook (alias for whatsapp_webhook)"""
    return await whatsapp_webhook(request, Body, From, MessageSid)


@app.get("/tasks")
async def list_tasks(project_id: str | None = None):
    client = get_todoist_client()
    tasks = await client.get_tasks(project_id)
    return {"tasks": [t.model_dump() for t in tasks]}