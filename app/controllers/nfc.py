from fastapi import APIRouter, HTTPException, status, Body, Request, BackgroundTasks
from app.utils.firebase_config import db
from app.schemas.schemas import NFCRequest, AccessResponse
from datetime import datetime
import pytz

router = APIRouter(tags=["NFC"])

def registrar_entrada(dashboard_ref, member_data, plan_name, now_str, membership):
    print(f"[LOG] Registrando ENTRADA para {member_data['name']} ({member_data['id']}) a las {now_str}")
    dashboard_ref.set({
        "miembro": {
            "id": member_data["id"],
            "name": member_data["name"],
            "email": member_data["email"],
            "plan": plan_name,
            "entrada": now_str,
            "salida": None,
            "tiempo_total": None,
            "end_date": membership["end_date"]
        }
    })
    print(f"[LOG] ENTRADA registrada exitosamente")

def registrar_salida(dashboard_ref, entrada_str, salida_str):
    print(f"[LOG] Registrando SALIDA... Entrada: {entrada_str}, Salida: {salida_str}")
    entrada_dt = datetime.strptime(entrada_str, "%Y-%m-%d %H:%M:%S")
    salida_dt = datetime.strptime(salida_str, "%Y-%m-%d %H:%M:%S")
    duracion = str(salida_dt - entrada_dt)

    dashboard_ref.update({
        "miembro.salida": salida_str,
        "miembro.tiempo_total": duracion
    })
    print(f"[LOG] SALIDA registrada. Duración dentro: {duracion}")
    return duracion

@router.post("/access", response_model=AccessResponse)
async def check_access(request: Request, background_tasks: BackgroundTasks, req: NFCRequest = Body(...)):
    print(f"[INICIO] Solicitud recibida para NFC ID: {req.nfc_id}")

    if not req.nfc_id or len(req.nfc_id.strip()) < 6:
        print(f"[ERROR] NFC ID inválido")
        raise HTTPException(status_code=400, detail="ID NFC inválido o vacío")

    # Buscar miembro por nfc_id
    member_docs = db.collection("members").where("nfc_id", "==", req.nfc_id).get()
    if not member_docs:
        print(f"[ERROR] Miembro con NFC ID {req.nfc_id} no encontrado")
        raise HTTPException(status_code=404, detail="Miembro no encontrado")

    member_doc = member_docs[0]
    member_data = member_doc.to_dict()
    member_id = member_doc.id
    member_data["id"] = member_id

    print(f"[LOG] Miembro encontrado: {member_data['name']} ({member_id})")

    # Buscar membresía activa con user_id
    memberships = db.collection("user_memberships")\
        .where("user_id", "==", member_id)\
        .where("status", "==", "active")\
        .get()

    if not memberships:
        print(f"[ERROR] No tiene membresía activa")
        return AccessResponse(
            id=req.nfc_id,
            name=member_data["name"],
            status=member_data["status"],
            access_granted=False,
            message="No tiene membresía activa"
        )

    membership = memberships[0].to_dict()
    plan_id = membership["plan_id"]
    end_date = datetime.strptime(membership["end_date"], "%Y-%m-%d").date()
    today = datetime.now(pytz.timezone("America/La_Paz")).date()

    if today > end_date:
        print(f"[ERROR] Membresía expirada el {membership['end_date']}")
        return AccessResponse(
            id=req.nfc_id,
            name=member_data["name"],
            status=member_data["status"],
            access_granted=False,
            message="La membresía ha expirado"
        )

    # Obtener información del plan
    plan = db.collection("membership_plans").document(plan_id).get()
    plan_data = plan.to_dict() if plan.exists else {}
    plan_name = plan_data.get("name", "")

    print(f"[LOG] Plan activo: {plan_name}, válido hasta {membership['end_date']}")

    # Acceder al dashboard usando el NFC ID como ID de documento
    dashboard_ref = db.collection("dashboard").document(req.nfc_id)
    dashboard_doc = dashboard_ref.get()
    now_str = datetime.now(pytz.timezone("America/La_Paz")).strftime("%Y-%m-%d %H:%M:%S")

    if dashboard_doc.exists:
        dashboard_data = dashboard_doc.to_dict()
        if dashboard_data["miembro"].get("entrada") and not dashboard_data["miembro"].get("salida"):
            entrada_str = dashboard_data["miembro"]["entrada"]
            salida_str = now_str
            duracion = str(datetime.strptime(salida_str, "%Y-%m-%d %H:%M:%S") -
                           datetime.strptime(entrada_str, "%Y-%m-%d %H:%M:%S"))

            print(f"[LOG] Usuario ya estaba dentro. Procesando salida...")

            background_tasks.add_task(registrar_salida, dashboard_ref, entrada_str, salida_str)

            return AccessResponse(
                id=req.nfc_id,
                name=member_data["name"],
                status=member_data["status"],
                access_granted=True,
                message=f"Salida registrada. Tiempo dentro: {duracion}",
                plan=plan_name,
                end_date=membership["end_date"]
            )

    print(f"[LOG] Usuario no estaba dentro. Registrando nueva entrada...")

    background_tasks.add_task(registrar_entrada, dashboard_ref, member_data, plan_name, now_str, membership)

    return AccessResponse(
        id=req.nfc_id,
        name=member_data["name"],
        status=member_data["status"],
        access_granted=True,
        message="Entrada registrada",
        plan=plan_name,
        end_date=membership["end_date"]
    )
