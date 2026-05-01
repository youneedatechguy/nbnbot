from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging

from .lookup_api import LookupRequest, get_lookup_service, format_lookup_message
from bot.nbn_service import NBNService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NBN Address Lookup Bot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-nbn-lookup-bot"}


@app.post("/lookup")
async def lookup(request: LookupRequest, service: NBNService = Depends(get_lookup_service)):
    results = await service.lookup(request.address)
    message = format_lookup_message(request.address, results)
    return {"message": message}
