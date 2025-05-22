from fastapi import APIRouter, HTTPException, status, Body, Request
from app.utils.firebase_config import db
from app.schemas.schemas import NFCRequest, AccessResponse

router = APIRouter(
    tags=["NFC"],
)

@router.post(
    "/access",
    response_model=AccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Verificar acceso mediante NFC",
    description="""
Consulta el estado de acceso de un miembro registrado utilizando su ID de tarjeta NFC.  
Devuelve el nombre del usuario, estado actual y si tiene acceso autorizado o no.
"""
)
async def check_access(
    request: Request,
    req: NFCRequest = Body(...)
):
    # Log del método y path para debug
    print(f"👉 Método recibido: {request.method}")
    print(f"📦 Payload recibido: {req}")

    # Validación básica del ID
    if not req.nfc_id or len(req.nfc_id.strip()) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID NFC inválido o vacío"
        )

    # Consulta en Firestore
    doc = db.collection("members").document(req.nfc_id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado"
        )

    # Procesamiento de datos
    data = doc.to_dict()
    granted = data.get("status", "").lower() == "activo"

    return AccessResponse(
        id=req.nfc_id,
        name=data.get("name", ""),
        status=data.get("status", ""),
        access_granted=granted,
        message="Access granted" if granted else "Access denied"
    )
