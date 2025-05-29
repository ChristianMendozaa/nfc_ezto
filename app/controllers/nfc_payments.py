from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import pytz

from app.utils.firebase_config import db

router = APIRouter(prefix="/payments", tags=["Payments"])

class PaymentRequest(BaseModel):
    nfc_id: str
    plan_id: str

class ProductPaymentRequest(BaseModel):
    nfc_id: str
    product_id: str


def update_monthly_revenue(amount: float):
    now = datetime.now(pytz.timezone("America/La_Paz"))
    year_month = now.strftime("%Y-%m")

    doc_ref = db.collection("dashboard").document("registro_general")
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        ingresos = data.get("monthly_revenue", {})
        ingresos[year_month] = ingresos.get(year_month, 0) + amount
        doc_ref.update({"monthly_revenue": ingresos})
    else:
        doc_ref.set({"monthly_revenue": {year_month: amount}})


@router.post("/membership")
async def register_membership_payment(data: PaymentRequest):
    member_docs = db.collection("members").where("nfc_id", "==", data.nfc_id).get()
    if not member_docs:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")

    member_doc = member_docs[0]
    member_data = member_doc.to_dict()
    member_id = member_doc.id

    plan_doc = db.collection("membership_plans").document(data.plan_id).get()
    if not plan_doc.exists:
        raise HTTPException(status_code=404, detail="Plan de membresía no encontrado")

    plan = plan_doc.to_dict()
    plan_price = plan.get("price", 0)
    plan_duration = plan.get("duration_months", 1)
    plan_name = plan.get("name", "")

    saldo_actual = member_data.get("dinero", 0)
    if saldo_actual < plan_price:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    nuevo_saldo = saldo_actual - plan_price
    db.collection("members").document(member_id).update({"dinero": nuevo_saldo})

    la_paz_tz = pytz.timezone("America/La_Paz")
    today = datetime.now(la_paz_tz).date()

    # Buscar membresía activa actual
    membership_query = db.collection("user_memberships").where("user_id", "==", member_id).where("status", "==", "active").get()

    if membership_query:
        existing_doc = membership_query[0]
        existing_data = existing_doc.to_dict()
        current_end_date = datetime.strptime(existing_data["end_date"], "%Y-%m-%d").date()
        # Si ya venció, empieza desde hoy; si no, suma al final
        base_date = max(today, current_end_date)
    else:
        base_date = today

    # Calcular nuevo end_date sumando meses (aprox. 30 días por mes)
    end_date = base_date + timedelta(days=plan_duration * 30)

    membership_data = {
        "user_id": member_id,
        "plan_id": data.plan_id,
        "status": "active",
        "start_date": today.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "auto_renew": True,
        "final_price": plan_price,
        "promotion_id": None,
    }

    if membership_query:
        db.collection("user_memberships").document(existing_doc.id).update(membership_data)
    else:
        db.collection("user_memberships").add(membership_data)

    db.collection("payment_logs").add({
        "member_id": member_id,
        "name": member_data.get("name", ""),
        "plan_id": data.plan_id,
        "plan_name": plan_name,
        "amount": plan_price,
        "category": "membership",
        "timestamp": datetime.now(la_paz_tz).isoformat()
    })

    update_monthly_revenue(plan_price)

    return {"message": "Pago y membresía registrados correctamente", "new_balance": nuevo_saldo}


@router.post("/product")
async def register_product_payment(data: ProductPaymentRequest):
    member_docs = db.collection("members").where("nfc_id", "==", data.nfc_id).get()
    if not member_docs:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")

    member_doc = member_docs[0]
    member_data = member_doc.to_dict()
    member_id = member_doc.id

    # Obtener producto y su precio
    product_doc = db.collection("products").document(data.product_id).get()
    if not product_doc.exists:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    product = product_doc.to_dict()
    sale_price = product.get("sale_price", 0)

    saldo_actual = member_data.get("dinero", 0)
    if saldo_actual < sale_price:
        raise HTTPException(status_code=400, detail="Saldo insuficiente")

    nuevo_saldo = saldo_actual - sale_price
    db.collection("members").document(member_id).update({"dinero": nuevo_saldo})

    db.collection("payment_logs").add({
        "member_id": member_id,
        "name": member_data.get("name", ""),
        "product_id": data.product_id,
        "product_name": product.get("name", ""),
        "amount": sale_price,
        "category": "product",
        "timestamp": datetime.now(pytz.timezone("America/La_Paz")).isoformat()
    })

    update_monthly_revenue(sale_price)

    return {"message": "Pago de producto registrado correctamente", "new_balance": nuevo_saldo}


@router.get("/membership-plans")
async def get_membership_plans():
    plans = db.collection("membership_plans").stream()
    return [plan.to_dict() for plan in plans]


@router.get("/products")
async def get_products():
    products = db.collection("products").stream()
    return [product.to_dict() for product in products]


@router.get("/history")
async def get_payment_history():
    docs = db.collection("payment_logs").order_by("timestamp", direction="DESCENDING").stream()
    return [doc.to_dict() for doc in docs]
