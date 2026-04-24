# WhatsApp-Todoist Bot Deployment Guide (Baileys)

## Overview

Deploy the WhatsApp-Todoist integration bot to dockerhost using Baileys (free, self-hosted WhatsApp).

**Uses Baileys (pyaileys)** - No paid Twilio account required!

## Prerequisites

### 1. Todoist API Token
1. Go to [Todoist Integrations](https://todoist.com/prefs/integrations)
2. Scroll to "API token" section
3. Copy your API token

### 2. WhatsApp Number
- Use any WhatsApp number you own
- No special business account needed
- Initial QR code scan required to link the bot

### 3. OpenAI API Key
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (starts with `sk-`)

## Deployment Steps

### 1. Configure Environment Variables

In Portainer (or your `.env` file), set:

```bash
# Todoist API
TODOIST_API_TOKEN=your_todoist_token_here

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o-mini

# Optional: OpenRouter (for model fallback)
# OPENROUTER_API_KEY=your_openrouter_key
# MODEL_PROVIDER=openrouter

# Optional: Redis (for conversation context)
# REDIS_URL=redis://localhost:6379
```

### 2. Build and Deploy

```bash
cd /mnt/apps/yambabroadband/api

# Build the container
docker-compose build

# Start the service
docker-compose up -d

# Check logs - you should see QR code for initial WhatsApp linking
docker-compose logs -f
```

### 3. Link WhatsApp (Initial Setup)

1. When the container starts, check logs for the QR code:
   ```bash
   docker-compose logs -f
   ```

2. You will see ASCII QR code in the logs

3. Open WhatsApp on your phone → Settings → Linked Devices → Link a Device

4. Scan the QR code from the logs

5. Session is persisted in Docker volume (`whatsapp-auth`)

### 4. Test the Bot

Send a WhatsApp message to your linked number:

```
help
```

You should receive a response with available commands.

Test task creation:
```
Create a task to buy milk tomorrow
```

Test task listing:
```
Show my tasks
```

## Service Management

### Check Status
```bash
docker-compose ps
```

### View Logs
```bash
docker-compose logs -f
```

### Restart Service
```bash
docker-compose restart
```

### Stop Service
```bash
docker-compose stop
```

### Update and Redeploy
```bash
git pull
docker-compose build
docker-compose up -d
```

## API Endpoints

The bot exposes these endpoints:

- **GET /health** - Health check (shows WhatsApp connection status)
- **GET /tasks** - List tasks via HTTP (testing only)

## Initial QR Code Linking

When deploying for the first time or after session reset:

1. Start the container
2. Watch logs: `docker-compose logs -f`
3. Find the QR code in the output
4. Scan with WhatsApp

The session will be automatically saved to the Docker volume.

**To reset WhatsApp linkage:**
```bash
docker-compose down
docker volume rm yambabroadband_whatsapp-auth
docker-compose up -d
```

## Testing Locally (Development)

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env

# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn app.main:app --reload --port 8000

# You'll see QR code in terminal for WhatsApp linking
```

## Troubleshooting

### Bot not responding
1. Check logs: `docker-compose logs -f`
2. Verify WhatsApp is linked (check health endpoint)
3. Test health endpoint: `curl http://localhost:8001/health`
4. Verify environment variables are set correctly

### WhatsApp disconnected
1. Restart the container: `docker-compose restart`
2. Check if session volume is working: `docker volume inspect yambabroadband_whatsapp-auth`
3. If session is corrupted, reset: `docker volume rm yambabroadband_whatsapp-auth && docker-compose up -d`

### Authentication errors
- **Todoist**: Check `TODOIST_API_TOKEN` is valid
- **OpenAI**: Verify `OPENAI_API_KEY` and check billing/quota

### QR Code not appearing
1. Check if container started: `docker-compose ps`
2. Check logs for errors: `docker-compose logs | tail -50`

## Security Considerations

- WhatsApp session credentials are stored in Docker volume
- API keys should be set via Portainer environment variables
- Consider using Docker secrets for production

## Cost Comparison

| Service | Cost |
|---------|------|
| Baileys (WhatsApp) | Free |
| OpenAI gpt-4o-mini | ~$0.15/1M input, $0.60/1M output |
| Todoist API | Free |
| Redis (optional) | Free (self-hosted) |

**Total: ~$5-15/month for moderate OpenAI usage**

## Advantages over Twilio

1. **No paid account required** - Use your existing WhatsApp
2. **No webhook configuration** - Direct connection to WhatsApp
3. **Free for personal use** - No per-message costs
4. **Simpler setup** - Just scan QR code

## Next Steps (Phase 4)

See [YAM-44](/YAM/issues/YAM-44) for:
- Enhanced Todoist Client integration
- Task update/move/complete operations
- Project management
- Better error handling