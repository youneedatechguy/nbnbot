const axios = require("axios");
const qrcode = require("qrcode-terminal");

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");

const PYTHON_LOOKUP_URL =
  process.env.PYTHON_LOOKUP_URL ||
  "http://whatsapp-nbn-lookup-bot:8000/lookup";

const AUTH_DIR = process.env.BAILEYS_AUTH_DIR || "./auth";

function extractTextFromMessage(message) {
  if (!message) return null;
  if (message.conversation) return message.conversation;
  if (message.extendedTextMessage?.text) return message.extendedTextMessage.text;
  if (message.imageMessage?.caption) return message.imageMessage.caption;
  return null;
}

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect } = update;

    if (update.qr) {
      console.log("=== SCAN THIS QR CODE IN WHATSAPP ===");
      qrcode.generate(update.qr, { small: true });
      console.log("=== QR CODE END ===");
    }

    if (connection === "open") {
      console.log("WhatsApp connection established and ready.");
    }

    if (connection === "close") {
      const reason =
        lastDisconnect?.error?.output?.statusCode ??
        lastDisconnect?.reason;
      const loggedOut = reason === DisconnectReason.loggedOut;

      if (loggedOut) {
        console.log("WhatsApp logged out. Stopping.");
        process.exit(0);
      }

      console.log("WhatsApp connection closed; restarting container...");
      process.exit(1);
    }
  });

  sock.ev.on("messages.upsert", async (m) => {
    const msg = m?.messages?.[0];
    if (!msg) return;

    const jid = msg.key?.remoteJid;
    if (!jid) return;
    if (msg.key?.fromMe) return;
    if (msg.message?.protocolMessage) return;

    const text = extractTextFromMessage(msg.message);
    if (!text) return;

    try {
      const resp = await axios.post(
        PYTHON_LOOKUP_URL,
        { address: text },
        { timeout: 20000 }
      );
      const replyText =
        typeof resp.data === "string" ? resp.data : resp.data?.message;

      if (!replyText) return;
      try {
        await sock.sendMessage(jid, { text: replyText });
      } catch (err) {
        console.error("Failed to send reply to", jid, ":", err?.message);
      }
    } catch (err) {
      console.error("Lookup failed for:", text, "-", err?.message);
      try {
        await sock.sendMessage(
          jid,
          {
            text: "Sorry, an error occurred while looking up NBN availability.",
          }
        );
      } catch (sendErr) {
        console.error(
          "Failed to send error reply to",
          jid,
          ":",
          sendErr?.message
        );
      }
    }
  });
}

if (require.main === module) {
  start().catch((err) => {
    console.error(
      "Fatal: failed to start WhatsApp socket:",
      err?.message || err
    );
    process.exit(1);
  });
}

module.exports = { start };
