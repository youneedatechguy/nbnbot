from pydantic import BaseModel


class Settings(BaseModel):
    todoist_api_token: str | None = None
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None
    
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_number: str | None = None
    
    model_provider: str = "openai"
    model_name: str = "gpt-4o-mini"
    
    mock_todoist: bool = False


def load_settings() -> Settings:
    from os import getenv
    
    return Settings(
        todoist_api_token=getenv("TODOIST_API_TOKEN"),
        openai_api_key=getenv("OPENAI_API_KEY"),
        openrouter_api_key=getenv("OPENROUTER_API_KEY"),
        twilio_account_sid=getenv("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=getenv("TWILIO_AUTH_TOKEN"),
        twilio_whatsapp_number=getenv("TWILIO_WHATSAPP_NUMBER"),
        model_provider=getenv("MODEL_PROVIDER", "openai"),
        model_name=getenv("MODEL_NAME", "gpt-4o-mini"),
        mock_todoist=getenv("MOCK_TODOIST", "false").lower() == "true",
    )


settings = load_settings()