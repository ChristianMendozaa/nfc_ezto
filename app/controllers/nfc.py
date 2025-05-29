from fastapi import APIRouter, HTTPException, Body, Request, BackgroundTasks, Query
from app.utils.firebase_config import db
from app.schemas.schemas import NFCRequest, AccessResponse
from datetime import datetime, timedelta
import pytz

router = APIRouter(tags=["NFC"])

@router.get("/access/logs")
async def get_all_access_logs(limit: int = Query(50), skip: int = Query(0)):
    docs = db.collection("access_logs").order_by("timestamp", direction="DESCENDING").offset(skip).limit(limit).stream()
    return [doc.to_dict() for doc in docs]

@router.get("/access/logs/{user_id}")
async def get_access_logs_by_user(user_id: str):
    docs = db.collection("access_logs").where("user_id", "==", user_id).order_by("timestamp", direction="DESCENDING").stream()
    return [doc.to_dict() for doc in docs]

@router.get("/access/alerts")
async def get_all_alerts(limit: int = Query(50), skip: int = Query(0)):
    docs = db.collection("access_alerts").order_by("timestamp", direction="DESCENDING").offset(skip).limit(limit).stream()
    return [doc.to_dict() for doc in docs]

@router.get("/access/alerts/{name}")
async def get_alerts_by_name(name: str):
    docs = db.collection("access_alerts").where("name", "==", name).order_by("timestamp", direction="DESCENDING").stream()
    return [doc.to_dict() for doc in docs]

def registrar_entrada(dashboard_ref, member_data, plan_name, now_str, membership, acceso_id):
    dashboard_ref.set({
        "accesos": {
            acceso_id: {
                "id": member_data["id"],
                "name": member_data["name"],
                "email": member_data["email"],
                "plan": plan_name,
                "entrada": now_str,
                "salida": None,
                "tiempo_total": None,
                "end_date": membership["end_date"]
            }
        }
    }, merge=True)

def registrar_salida(dashboard_ref, acceso_id, entrada_str, salida_str):
    entrada_dt = datetime.strptime(entrada_str, "%Y-%m-%d %H:%M:%S")
    salida_dt = datetime.strptime(salida_str, "%Y-%m-%d %H:%M:%S")
    duracion = str(salida_dt - entrada_dt)
    dashboard_ref.update({
        f"accesos.{acceso_id}.salida": salida_str,
        f"accesos.{acceso_id}.tiempo_total": duracion
    })

def guardar_access_log(member_data, nfc_id, status, reason=None):
    db.collection("access_logs").add({
        "user_id": member_data["id"],
        "name": member_data["name"],
        "nfc_id": nfc_id,
        "timestamp": datetime.now(pytz.timezone("America/La_Paz")).isoformat(),
        "status": status,
        "reason": reason,
        "device_type": "card"
    })

def generar_alerta(nombre, tipo, ubicacion):
    db.collection("access_alerts").add({
        "name": nombre,
        "type": tipo,
        "location": ubicacion,
        "timestamp": datetime.now(pytz.timezone("America/La_Paz")).isoformat()
    })

def actualizar_estadisticas_dashboard():
    dashboard_ref = db.collection("dashboard").document("registro_general")
    now = datetime.now(pytz.timezone("America/La_Paz"))
    today_str = now.strftime("%Y-%m-%d")

    try:
        doc = dashboard_ref.get()
        accesos = doc.to_dict().get("accesos", {}) if doc.exists else {}

        active_members = sum(1 for a in accesos.values() if a.get("entrada") and not a.get("salida"))
        daily_count = sum(1 for a in accesos.values()
                          if a.get("entrada", "").startswith(today_str) or a.get("salida", "").startswith(today_str))

        activity_per_day = doc.to_dict().get("activity_per_day", {})
        activity_per_day[today_str] = daily_count

        dashboard_ref.update({
            "stats.activeMembers": active_members,
            "stats.dailyActivity": daily_count,
            "activity_per_day": activity_per_day,
            "updated_at": now.isoformat()
        })
    except Exception as e:
        print(f"[STATS ERROR] {e}")

@router.post("/access", response_model=AccessResponse)
async def check_access(request: Request, background_tasks: BackgroundTasks, req: NFCRequest = Body(...)):
    if not req.nfc_id or len(req.nfc_id.strip()) < 6:
        raise HTTPException(status_code=400, detail="ID NFC inválido")

    now = datetime.now(pytz.timezone("America/La_Paz"))
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    acceso_id = now.strftime("%Y%m%d%H%M%S")

    member_docs = db.collection("members").where("nfc_id", "==", req.nfc_id).get()
    if not member_docs:
        background_tasks.add_task(guardar_access_log, {"id": None, "name": "Unknown"}, req.nfc_id, "denied", "unknown_nfc")
        background_tasks.add_task(generar_alerta, "Unknown", "Unknown NFC", "Acceso General")
        raise HTTPException(status_code=404, detail="Miembro no encontrado")

    member_doc = member_docs[0]
    member_data = member_doc.to_dict()
    member_data["id"] = member_doc.id

    memberships = db.collection("user_memberships").where("user_id", "==", member_data["id"]).where("status", "==", "active").get()
    if not memberships:
        background_tasks.add_task(guardar_access_log, member_data, req.nfc_id, "denied", "no_active_membership")
        background_tasks.add_task(generar_alerta, member_data["name"], "No Active Membership", "Acceso General")
        return AccessResponse(id=req.nfc_id, name=member_data["name"], status=member_data["status"], access_granted=False, message="No tiene membresía activa")

    membership = memberships[0].to_dict()
    end_date = datetime.strptime(membership["end_date"], "%Y-%m-%d").date()
    if now.date() > end_date:
        background_tasks.add_task(guardar_access_log, member_data, req.nfc_id, "denied", "expired_membership")
        background_tasks.add_task(generar_alerta, member_data["name"], "Membership Expired", "Acceso General")
        return AccessResponse(id=req.nfc_id, name=member_data["name"], status=member_data["status"], access_granted=False, message="La membresía ha expirado")

    plan = db.collection("membership_plans").document(membership["plan_id"]).get()
    plan_name = plan.to_dict().get("name", "") if plan.exists else ""
    dashboard_ref = db.collection("dashboard").document("registro_general")

    try:
        accesos = dashboard_ref.get().to_dict().get("accesos", {})
    except:
        accesos = {}

    for key, data in accesos.items():
        if data.get("id") == member_data["id"] and data.get("entrada") and not data.get("salida"):
            background_tasks.add_task(registrar_salida, dashboard_ref, key, data["entrada"], now_str)
            background_tasks.add_task(guardar_access_log, member_data, req.nfc_id, "granted")
            background_tasks.add_task(actualizar_estadisticas_dashboard)
            duracion = str(datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S") - datetime.strptime(data["entrada"], "%Y-%m-%d %H:%M:%S"))
            return AccessResponse(id=req.nfc_id, name=member_data["name"], status=member_data["status"], access_granted=True, message=f"Salida registrada. Tiempo dentro: {duracion}", plan=plan_name, end_date=membership["end_date"])

    background_tasks.add_task(registrar_entrada, dashboard_ref, member_data, plan_name, now_str, membership, acceso_id)
    background_tasks.add_task(guardar_access_log, member_data, req.nfc_id, "granted")
    background_tasks.add_task(actualizar_estadisticas_dashboard)
    return AccessResponse(id=req.nfc_id, name=member_data["name"], status=member_data["status"], access_granted=True, message="Entrada registrada", plan=plan_name, end_date=membership["end_date"])
