import makeWASocket, { useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys'
import express from 'express'
import bodyParser from 'body-parser'
import qrcode from 'qrcode-terminal' // <--- Nueva importación

const app = express()
app.use(bodyParser.json())

let sock = null
let isConnected = false

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info')
    
    sock = makeWASocket.default ? makeWASocket.default({
        auth: state,
        printQRInTerminal: false // <--- Lo ponemos en false porque lo haremos manualmente
    }) : makeWASocket({
        auth: state,
        printQRInTerminal: false
    })

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update
        
        // Si hay un QR, lo pintamos en la terminal
        if (qr) {
            console.log('Escanea este QR con WhatsApp:')
            qrcode.generate(qr, { small: true }) // <--- Esto genera el dibujo del QR
        }
        
        if (connection === 'close') {
            const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut
            console.log('Conexión cerrada. Reconectando:', shouldReconnect)
            if (shouldReconnect) {
                connectToWhatsApp()
            }
            isConnected = false
        } else if (connection === 'open') {
            console.log('Conectado a WhatsApp!')
            isConnected = true
        }
    })

    sock.ev.on('creds.update', saveCreds)
}

app.post('/send-message', async (req, res) => {
    try {
        if (!isConnected) {
            return res.status(503).json({ error: 'WhatsApp no conectado' })
        }
        const { phone, message } = req.body
        const jid = phone.includes('@') ? phone : `${phone}@s.whatsapp.net`
        await sock.sendMessage(jid, { text: message })
        res.json({ status: 'sent', to: phone })
    } catch (error) {
        res.status(500).json({ error: error.message })
    }
})

app.get('/status', (req, res) => {
    res.json({ connected: isConnected })
})

const PORT = 3000
app.listen(PORT, () => {
    console.log(`Servidor corriendo en http://localhost:${PORT}`)
    connectToWhatsApp()
})