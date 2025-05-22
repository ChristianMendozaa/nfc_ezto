import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.routers.nfc import router as nfc_router

# --- OpenAPI metadata ---
app = FastAPI(
    title="NFC-Service",
    description="""
    Microservicio para el manejo de tarjetas NFC.  
    Incluye funcionalidades de lectura, escritura y validación de tags.
    """,
    version="1.0.0",
    contact={
        "name": "Equipo de Desarrollo",
        "url": "https://github.com/tu-org/nfc-service",
        "email": "soporte@tuempresa.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    terms_of_service="https://tuempresa.com/terminos",
    root_path="/nfc",
)

# --- CORS middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- Rutas principales ---
app.include_router(
    nfc_router,
    tags=["NFC"],
)

# --- Modelo para salud ---
class HealthResponse(BaseModel):
    status: str

# --- Endpoint de salud ---
@app.get("/health", tags=["Health"], summary="Verifica el estado del servicio", response_model=HealthResponse)
async def health():
    """
    Verifica si el microservicio está en ejecución.
    Retorna un JSON con el estado `"ok"`.
    """
    return {"status": "ok"}
