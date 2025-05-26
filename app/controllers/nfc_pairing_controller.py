from fastapi import APIRouter, HTTPException, status, Body
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime, timedelta
from app.utils.firebase_config import db

router = APIRouter(tags=["NFC Pairing"])

# --- SCHEMAS ---

class PairingCodeRequest(BaseModel):
    member_id: str

class NFCLinkRequest(BaseModel):
    pairing_code: str
    nfc_id: str


# --- ENDPOINT 1: Generar código de emparejamiento ---

@router.post("/pairing-code")
async def generate_pairing_code(payload: PairingCodeRequest):
    pairing_code = str(uuid4())[:6]  # código corto único
    doc_ref = db.collection("pending_nfc_links").document(pairing_code)

    # Verifica si el miembro ya tiene una tarjeta NFC
    member_ref = db.collection("members").document(payload.member_id)
    member_doc = member_ref.get()
    if not member_doc.exists:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")

    member_data = member_doc.to_dict()
    if member_data.get("nfc_id"):
        raise HTTPException(status_code=400, detail="El miembro ya tiene una tarjeta NFC vinculada")

    # Crea el documento temporal
    doc_ref.set({
        "member_id": payload.member_id,
        "created_at": datetime.utcnow().isoformat(),
        "status": "waiting"
    })

    return {
        "pairing_code": pairing_code,
        "message": "Código de emparejamiento generado. Úsalo en la app móvil para vincular la tarjeta NFC."
    }


# --- ENDPOINT 2: Vincular tarjeta desde la app móvil ---

@router.post("/link")
async def link_nfc_card(payload: NFCLinkRequest):
    doc_ref = db.collection("pending_nfc_links").document(payload.pairing_code)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Código de emparejamiento inválido o expirado")

    data = doc.to_dict()

    # Opcional: controlar expiración (ej. 5 minutos)
    created_time = datetime.fromisoformat(data["created_at"])
    if datetime.utcnow() - created_time > timedelta(minutes=5):
        raise HTTPException(status_code=410, detail="El código de emparejamiento ha expirado")

    member_id = data["member_id"]
    member_ref = db.collection("members").document(member_id)
    member_doc = member_ref.get()

    if not member_doc.exists:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")

    # Verificar si el NFC ya está en uso por otro miembro
    nfc_check = db.collection("members").where("nfc_id", "==", payload.nfc_id).get()
    if nfc_check:
        raise HTTPException(status_code=409, detail="Esta tarjeta NFC ya está vinculada a otro miembro")

    # Actualiza el miembro con el nuevo nfc_id
    member_ref.update({
        "nfc_id": payload.nfc_id,
        "status": "activo"
    })

    # Borra el código o marca como usado
    doc_ref.delete()

    return {
        "message": "Tarjeta NFC vinculada correctamente al miembro",
        "member_id": member_id,
        "nfc_id": payload.nfc_id
    }
