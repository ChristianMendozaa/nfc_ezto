from pydantic import BaseModel, Field
from typing import Optional

class NFCRequest(BaseModel):
    nfc_id: str = Field(..., description="ID único de la tarjeta NFC del usuario")

class AccessResponse(BaseModel):
    id: str
    name: str
    status: str
    access_granted: bool
    message: str
    plan: Optional[str] = None
    end_date: Optional[str] = None