from pydantic import BaseModel, ConfigDict

from bot.nbn_service import NBNService, NBNResult


class LookupRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    address: str


def get_lookup_service() -> NBNService:
    return NBNService()


def format_lookup_message(address: str, results: list[NBNResult]) -> str:
    if not results:
        return f"📭 No NBN results found for:\n_{address}_\n\nThe address may not be in the NBN database or is not yet serviceable."

    lines = [f"📡 *NBN Availability for {address}*\n"]
    for result in results:
        lines.append(result.format_message())
        lines.append("")
    return "\n".join(lines).strip()
