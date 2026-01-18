from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from typing import List
from datetime import datetime


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://innovaitech-2026-salud.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL del servidor Baileys corriendo localmente
BAILEYS_API_URL = "https://paraphysate-raiden-fractus.ngrok-free.dev"

class WhatsAppRequest(BaseModel):
    patient_id: str
    message: str
    urgency_level: str
    phone_numbers: List[str]


class WhatsAppResponse(BaseModel):
    status: str
    patient_id: str
    recipients_count: int
    urgency_level: str
    failed_numbers: List[str] = []
    timestamp: str


def format_phone_number(phone: str) -> str:
    """Formatea número para WhatsApp (sin + ni guiones)"""
    # Remover espacios, guiones, paréntesis
    clean = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Remover el +
    if clean.startswith("+"):
        clean = clean[1:]
    
    # Si empieza con 0, removerlo (formato local Ecuador)
    if clean.startswith("0"):
        clean = "593" + clean[1:]
    
    # Si no tiene código de país, añadir 593 (Ecuador)
    if len(clean) == 9:  # número local sin código país
        clean = "593" + clean
    
    return clean


@app.post("/api/send-whatsapp", response_model=WhatsAppResponse)
async def send_whatsapp_emergency(data: WhatsAppRequest):
    """
    Envía mensajes de emergencia por WhatsApp usando Baileys.
    """
    
    # Verificar que Baileys está conectado
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            status_response = await client.get(f"{BAILEYS_API_URL}/status")
            status_data = status_response.json()
            
            if not status_data.get("connected"):
                raise HTTPException(
                    status_code=503,
                    detail="Servicio de WhatsApp no conectado. Escanea el QR primero."
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Servidor de WhatsApp no disponible. Inicia whatsapp-server.js"
            )
    
    sent_to = []
    failed = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for number in data.phone_numbers:
            try:
                formatted_number = format_phone_number(number)
                
                payload = {
                    "phone": formatted_number,
                    "message": data.message
                }
                
                response = await client.post(
                    f"{BAILEYS_API_URL}/send-message",
                    json=payload
                )
                
                if response.status_code == 200:
                    sent_to.append(number)
                else:
                    failed.append(number)
                    print(f"Error enviando a {number}: {response.text}")
                    
            except Exception as e:
                failed.append(number)
                print(f"Excepción enviando a {number}: {str(e)}")
    
    if len(sent_to) == 0:
        raise HTTPException(
            status_code=500,
            detail="No se pudo enviar a ningún contacto"
        )
    
    return WhatsAppResponse(
        status="sent" if len(failed) == 0 else "partial",
        patient_id=data.patient_id,
        recipients_count=len(sent_to),
        urgency_level=data.urgency_level,
        failed_numbers=failed,
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/health")
async def health_check():
    """Verifica estado del servicio"""
    return {"status": "healthy", "service": "CardioVida WhatsApp"}


@app.get("/whatsapp-status")
async def whatsapp_status():
    """Verifica si WhatsApp está conectado"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BAILEYS_API_URL}/status")
            return response.json()
    except:
        return {"connected": False, "error": "Baileys server not reachable"}