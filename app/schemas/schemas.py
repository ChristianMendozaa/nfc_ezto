from pydantic import BaseModel, Field

class NFCRequest(BaseModel):
    nfc_id: str = Field(..., description="ID único de la tarjeta NFC del usuario")

class AccessResponse(BaseModel):
    id: str = Field(..., description="ID de la tarjeta NFC utilizada")
    name: str = Field(..., description="Nombre del usuario registrado con la tarjeta")
    status: str = Field(..., description="Estado del usuario (e.g., activo, inactivo)")
    access_granted: bool = Field(..., description="Indica si el acceso fue concedido")
    message: str = Field(..., description="Mensaje con el resultado del intento de acceso")
