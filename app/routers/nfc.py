from fastapi import APIRouter, HTTPException, status
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
async def check_access(req: NFCRequest):
    """
    Verifica si un miembro con el ID NFC proporcionado tiene acceso autorizado.

    - **nfc_id**: ID único de la tarjeta NFC
    - **Retorna**: nombre, estado y resultado del acceso
    """
    doc = db.collection("members").document(req.nfc_id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    
    data = doc.to_dict()
    granted = data.get("status") == "activo"
    
    return AccessResponse(
        id=req.nfc_id,
        name=data.get("name", ""),
        status=data.get("status", ""),
        access_granted=granted,
        message="Access granted" if granted else "Access denied"
    )
