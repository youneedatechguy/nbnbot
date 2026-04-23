# WhatsApp-Todoist Bot Deployment Guide

## Overview
Deploy the WhatsApp-Todoist integration bot to dockerhost using Docker Compose.

## Prerequisites

### 1. Todoist API Token
1. Go to [Todoist Integrations](https://todoist.com/prefs/integrations)
2. Scroll to "API token" section
3. Copy your API token

### 2. Twilio WhatsApp Setup
1. Create a [Twilio account](https://www.twilio.com/console)
2. Get a WhatsApp-enabled phone number:
   - Go to Messaging → Try it out → Send a WhatsApp message
   - Follow the Twilio Sandbox setup instructions
   - Or purchase a WhatsApp Business number
3. Get credentials from [Twilio Console](https://console.twilio.com):
   - **Account SID**
   - **Auth Token**
   - **WhatsApp Number** (format: `whatsapp:+14155238886`)

### 3. OpenAI API Key
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (starts with `sk-`)

## Deployment Steps

### 1. Configure Environment Variables

In Portainer (or your `.env` file), set:

```bash
# Todoist
TODOIST_API_TOKEN=your_todoist_token_here

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o-mini

# Optional: OpenRouter (for model fallback)
# OPENROUTER_API_KEY=your_openrouter_key
# MODEL_PROVIDER=openrouter
```

### 2. Build and Deploy

```bash
cd /mnt/apps/yambabroadband/api

# Build the container
docker-compose build whatsapp-todoist-bot

# Start the service
docker-compose up -d whatsapp-todoist-bot

# Check logs
docker-compose logs -f whatsapp-todoist-bot
```

### 3. Configure Twilio Webhook

1. Go to [Twilio Console → Messaging → Settings](https://console.twilio.com/us1/develop/sms/settings/whatsapp-sender)
2. Under "Sandbox settings" or your WhatsApp number configuration
3. Set the webhook URL:
   ```
   https://your-domain.com/webhook/whatsapp
   ```
   Or if using the dockerhost IP:
   ```
   http://YOUR_DOCKERHOST_IP:8001/webhook/whatsapp
   ```
4. Method: **POST**
5. Save settings

### 4. Test the Bot

Send a WhatsApp message to your Twilio number:

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
docker-compose logs -f whatsapp-todoist-bot
```

### Restart Service
```bash
docker-compose restart whatsapp-todoist-bot
```

### Stop Service
```bash
docker-compose stop whatsapp-todoist-bot
```

### Update and Redeploy
```bash
git pull
docker-compose build whatsapp-todoist-bot
docker-compose up -d whatsapp-todoist-bot
```

## API Endpoints

The bot exposes these endpoints:

- **POST /webhook/whatsapp** - Twilio WhatsApp webhook (main entry point)
- **POST /webhook/twilio** - Alternative Twilio webhook
- **GET /health** - Health check endpoint
- **GET /tasks** - List tasks via HTTP (testing only)

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

# Test with curl
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"Body": "help", "From": "whatsapp:+1234567890"}'
```

## Troubleshooting

### Bot not responding
1. Check logs: `docker-compose logs -f whatsapp-todoist-bot`
2. Verify webhook URL in Twilio console
3. Test health endpoint: `curl http://localhost:8001/health`
4. Verify environment variables are set correctly

### Authentication errors
- **Todoist**: Check `TODOIST_API_TOKEN` is valid
- **OpenAI**: Verify `OPENAI_API_KEY` and check billing/quota
- **Twilio**: Confirm `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`

### Webhook not receiving messages
1. Verify Twilio webhook URL is correct and publicly accessible
2. Check firewall allows inbound traffic on port 8001
3. Test webhook manually with curl
4. Check Twilio debugger: https://console.twilio.com/us1/monitor/debugger

### Tasks not creating in Todoist
1. Verify `TODOIST_API_TOKEN` has write permissions
2. Check OpenAI API is responding (model availability)
3. Review logs for agent processing errors

## Security Considerations

⚠️ **Production Hardening** (Phase 2+):
- Add Twilio webhook signature validation
- Use HTTPS with valid SSL certificate
- Implement rate limiting
- Add user authentication/allowlist
- Monitor API usage and costs

## Cost Estimates

- **Twilio Sandbox**: Free (for testing)
- **Twilio WhatsApp Business**: ~$0.005 per message
- **OpenAI gpt-4o-mini**: ~$0.15 per 1M input tokens, $0.60 per 1M output tokens
- **Todoist API**: Free

Estimated monthly cost for moderate usage: **$5-15/month**

## Next Steps (Phase 2)

See [YAM-39](/YAM/issues/YAM-39) for:
- Enhanced agent with multi-model support
- Task update/move/complete operations
- Project management
- Better error handling
- Webhook signature validation
