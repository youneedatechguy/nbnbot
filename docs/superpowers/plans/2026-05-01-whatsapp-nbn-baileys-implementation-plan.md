# WhatsApp NBN lookup via Baileys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current WhatsApp integration with a Baileys-based bot that calls the Iperium-backed NBN lookup and replies in the same format as the Telegram bot.

**Architecture:** Add a new Node/Baileys container that connects to WhatsApp and forwards each inbound text message to a new FastAPI endpoint. The FastAPI endpoint calls `bot/nbn_service.py:NBNService.lookup()` and formats results using `NBNResult.format_message()` for exact output consistency.

**Tech Stack:** Node.js (Baileys), FastAPI (Python), Iperium client + Google Maps geocoder already in the repo.

---

### Task 1: Add FastAPI lookup endpoint

**Files:**
- Modify: `app/main.py`
- Create: `app/lookup_api.py`
- Test: `tests/test_lookup_api.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_lookup_api.py` with the following content (endpoint does not exist yet, so the test should fail):

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_lookup_service
from bot.nbn_service import NBNResult


class FakeNBNService:
    async def lookup(self, free_text_address: str):
        return [
            NBNResult(
                input_address=free_text_address,
                loc_id="LOC123",
                match=None,
                address="11 Wattle Drive, Yamba NSW 2464",
                technology="FTTP",
                serviceability=1,
                ports_free=None,
                ports_used=None,
                ports_total=None,
                service_class=None,
                fibre_on_demand=None,
            )
        ]


def test_lookup_endpoint_returns_formatted_message():
    app.dependency_overrides[get_lookup_service] = lambda: FakeNBNService()
    try:
        client = TestClient(app)
        resp = client.post("/lookup", json={"address": "11 Wattle Drive Yamba NSW 2464"})
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "📡" in data["message"]
        assert "LOC123" in data["message"]
        assert "FTTP" in data["message"]
        assert "Serviceable" in data["message"]
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest -q tests/test_lookup_api.py -v
```

Expected: FAIL (missing `/lookup` endpoint / missing symbols).

- [ ] **Step 3: Write minimal implementation**

Create `app/lookup_api.py`:

```python
from pydantic import BaseModel, ConfigDict

from bot.nbn_service import NBNService


class LookupRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    address: str


def get_lookup_service() -> NBNService:
    return NBNService()


def format_lookup_message(address: str, results: list) -> str:
    if not results:
        return f"📭 No NBN results found for:\n_{address}_\n\nThe address may not be in the NBN database or is not yet serviceable."

    lines = [f"📡 *NBN Availability for {address}*\n"]
    for result in results:
        lines.append(result.format_message())
        lines.append("")
    return "\n".join(lines).strip()
```

Update `app/main.py` to remove Twilio/Todoist wiring and add the `/lookup` endpoint. Replace the file with:

```python
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.lookup_api import LookupRequest, get_lookup_service, format_lookup_message
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
```

Notes:
- The Baileys service will send the returned text directly to WhatsApp.
- The endpoint uses FastAPI dependency injection so tests can override `get_lookup_service`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest -q tests/test_lookup_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/lookup_api.py tests/test_lookup_api.py
git commit -m "feat: add Baileys lookup API endpoint for NBN" 
```

### Task 2: Add Baileys WhatsApp service

**Files:**
- Create: `baileys/package.json`
- Create: `baileys/index.js`
- Create: `baileys/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Write failing test**

Skip automated tests for the Node runtime (no existing Node test harness in the repo). Instead, add a minimal “smoke” config check test by verifying the Node entrypoint exports no syntax errors. Create `baileys/smoke.js`:

```js
require("./index.js");
console.log("smoke-ok");
```

Run (expected FAIL until `baileys/index.js` exists):

```bash
node baileys/smoke.js
```

Expected: FAIL due to missing folder/file.

- [ ] **Step 2: Implement Baileys service**

Create `baileys/package.json`:

```json
{
  "name": "whatsapp-nbn-baileys",
  "private": true,
  "type": "commonjs",
  "version": "1.0.0",
  "main": "index.js",
  "dependencies": {
    "@whiskeysockets/baileys": "^6.7.0",
    "axios": "^1.6.8"
  }
}
```

Create `baileys/index.js`:

```js
const axios = require("axios");
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  jidNormalizedUser
} = require("@whiskeysockets/baileys");

const PYTHON_LOOKUP_URL = process.env.PYTHON_LOOKUP_URL || "http://whatsapp-nbn-lookup-bot:8000/lookup";
const AUTH_DIR = process.env.BAILEYS_AUTH_DIR || "./auth";

async function sendText(sock, jid, text) {
  await sock.sendMessage(jid, { text });
}

function extractTextFromMessage(message) {
  if (!message) return null;
  if (message.conversation) return message.conversation;
  if (message.extendedTextMessage && message.extendedTextMessage.text) return message.extendedTextMessage.text;
  if (message.imageMessage && message.imageMessage.caption) return message.imageMessage.caption;
  return null;
}

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: true
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect } = update;
    if (connection === "close") {
      const shouldReconnect = (lastDisconnect?.error)?.output?.statusCode !== DisconnectReason.loggedOut;
      if (shouldReconnect) start();
    }
  });

  sock.ev.on("messages.upsert", async (m) => {
    const msg = m?.messages?.[0];
    if (!msg) return;

    const jid = msg.key?.remoteJid;
    const fromMe = msg.key?.fromMe;
    if (!jid || fromMe) return;
    if (msg.message?.protocolMessage) return;

    const text = extractTextFromMessage(msg.message);
    if (!text) return;

    try {
      const resp = await axios.post(PYTHON_LOOKUP_URL, { address: text }, { timeout: 20000 });
      const replyText = typeof resp.data === "string" ? resp.data : resp.data?.message;
      if (!replyText) return;
      await sendText(sock, jid, replyText);
    } catch (err) {
      const fallback = "Sorry, an error occurred while looking up NBN availability.";
      await sendText(sock, jid, fallback);
    }
  });
}

start();
```

Create `baileys/Dockerfile`:

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json .
RUN npm install --omit=dev
COPY index.js ./
CMD ["node", "index.js"]
```

- [ ] **Step 3: Wire into docker-compose**

Modify `docker-compose.yml` to rename the Python service and add the Baileys service.

Replace the current service block with:

```yaml
services:
  whatsapp-nbn-lookup-bot:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: whatsapp-nbn-lookup-bot
    restart: unless-stopped
    ports:
      - "8001:8000"
    environment: []
    volumes:
      - analytics:/mnt/apps/yambabroadband/analytics
      - bot-logs:/var/log/yambabroadband
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  whatsapp-nbn-baileys:
    build:
      context: ./baileys
      dockerfile: Dockerfile
    container_name: whatsapp-nbn-baileys
    restart: unless-stopped
    environment:
      - PYTHON_LOOKUP_URL=http://whatsapp-nbn-lookup-bot:8000/lookup
      - BAILEYS_AUTH_DIR=/app/auth
    volumes:
      - baileys-auth:/app/auth
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  analytics:
    driver: local
  bot-logs:
    driver: local
  baileys-auth:
    driver: local
```

Notes:
- `docker-compose.yml` currently includes Todoist/Twilio env vars; they should be removed after the wiring change.
- The Baileys service prints a QR code in its logs for the first-time login.

- [ ] **Step 4: Run smoke**

Run:

```bash
docker compose up -d --build
docker compose logs -f whatsapp-nbn-baileys
```

Expected: Baileys prints a QR code and waits for pairing.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml baileys/
git commit -m "feat: add Baileys WhatsApp frontend for NBN lookup" 
```

### Task 3: Rename bot naming strings

**Files:**
- Modify: `WHATSAPP_DEPLOYMENT.md`
- Modify: `app/main.py` (health already changed in Task 1)

- [ ] **Step 1: Update documentation**

Update `WHATSAPP_DEPLOYMENT.md` to:
- Remove Twilio setup steps.
- Add Baileys setup steps: start container, scan QR in logs, send an address, observe NBN response.
- Update any service name references from `whatsapp-todoist-bot` to `whatsapp-nbn-lookup-bot`.

- [ ] **Step 2: Commit**

```bash
git add WHATSAPP_DEPLOYMENT.md
git commit -m "docs: update WhatsApp deployment for NBN lookup via Baileys"
```

### Task 4: Rebuild/restart and verify end-to-end

**Files:**
- none

- [ ] **Step 1: Rebuild**

Run:

```bash
docker compose up -d --build
```

- [ ] **Step 2: Verify health**

Run:

```bash
curl -sS http://localhost:8001/health
```

Expected:
- `"service": "whatsapp-nbn-lookup-bot"`

- [ ] **Step 3: Pair Baileys**

Run:

```bash
docker compose logs -f whatsapp-nbn-baileys
```

Expected:
- A QR code appears in terminal output or logs.

- [ ] **Step 4: Manual message test**

Send WhatsApp message with a known NSW/QLD/Yamba-like address (any free-text address you know should match).

Expected:
- Bot replies with `📡 *NBN Availability for ...*` and formatted fields.
