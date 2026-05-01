# WhatsApp NBN lookup via Baileys + Iperium

## Goal
Replace the current WhatsApp integration with a WhatsApp bot that lets users query NBN connection details by sending a free-text address. The WhatsApp bot must return results in the same format as the existing Telegram NBN bot.

## Non-goals
- Todoist functionality.
- Twilio webhooks/signature validation.
- Telegram support.

## High-level architecture

### 1) Baileys “frontend” service (Node)
- Runs Baileys, connects to WhatsApp, listens for incoming messages.
- For each incoming text message that is not a command, calls the Python API endpoint with:
  - `address`: raw message text.
  - `user`: sender identifier (for logging/correlation; not required for lookup).
- Sends the Python API response back to WhatsApp.

### 2) Python “lookup backend” (FastAPI)
- Exposes a minimal HTTP endpoint for address lookup.
- Implements lookup by calling `bot/nbn_service.py:NBNService.lookup()`.
- Formats responses using `NBNResult.format_message()` to match the Telegram bot output.

## Data flow
1. User sends an address in WhatsApp.
2. Baileys receives the message.
3. Baileys POSTs `{"address": "...", "user": "..."}` to Python `/lookup`.
4. Python:
   - validates input
   - calls Iperium via `NBNService`
   - if results are empty, returns a “no results found” message
   - otherwise returns the joined, formatted result blocks
5. Baileys sends the returned text to the user.

## Endpoints (Python)
### `POST /lookup`
Request:
```json
{
  "address": "free text address"
}
```
Response:
```json
{ "message": "formatted response text" }
```

## Bot naming changes
- Replace all user-facing naming that currently says “Todoist” with:
  - **NBN Address Lookup Bot**
- Update FastAPI `/health` output `service` field accordingly.

## Error handling behavior
- If Iperium raises `ValueError` for unmatchable address, return a user-friendly “address could not be matched” message.
- For unexpected errors, return a generic “try again later” message.

## Secrets / configuration
Python backend requires:
- `IPERIUM_EMAIL`
- `IPERIUM_PASSWORD`
Baileys service requires WhatsApp session credentials (implementation-defined, typically a local session volume).

## Testing
- Unit: validate that `NBNResult.format_message()` output for sample `NBNResult` objects matches expected Telegram formatting.
- Integration: manual test with a known address hitting `POST /lookup`, verifying the exact message body that Baileys will send.

## Implementation notes
- Keep changes minimal and localized: reuse `bot/nbn_service.py` and `NBNResult.format_message()` for formatting consistency.
- Remove Twilio-related wiring from Python once Baileys is introduced.
