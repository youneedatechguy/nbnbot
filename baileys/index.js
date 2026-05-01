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

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect } = update;

    if (update.qr) {
      qrcode.generate(update.qr, { small: true });
    }

    if (connection === "close") {
      const shouldReconnect =
        lastDisconnect?.error?.output?.statusCode !==
        DisconnectReason.loggedOut;
      if (shouldReconnect) start();
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
      await sock.sendMessage(jid, { text: replyText });
    } catch {
      await sock.sendMessage(
        jid,
        { text: "Sorry, an error occurred while looking up NBN availability." }
      );
    }
  });
}

if (require.main === module) {
  start();
}

module.exports = { start };
