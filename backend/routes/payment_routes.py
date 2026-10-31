"""
Payment API Endpoints
=====================
Routes for recording payments against invoices and querying payment history.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from middleware.auth import api_response, api_error, get_current_user, prevent_customer_idor
from services.payment_service import PaymentService

payment_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


@payment_bp.route("", methods=["GET"])
@jwt_required()
def list_payments():
    """Lists payments. Customers see only their own; staff/admin see all."""
    current_user = get_current_user()
    method = request.args.get("method")
    search = request.args.get("search")
    customer_id = current_user.id if current_user.role == "customer" else request.args.get("customer_id", type=int)

    payments = PaymentService.list_payments(customer_id=customer_id, method=method, search=search)
    return api_response(data=payments, status_code=200)


@payment_bp.route("", methods=["POST"])
@jwt_required()
def record_payment():
    """Records a payment against an invoice (both staff and customers paying their invoice)."""
    current_user = get_current_user()
    data = request.get_json() or {}

    payment, error = PaymentService.record_payment(data, user_id=current_user.id)
    if error:
        return api_error(error, 400)
    return api_response(data=payment, message=f"Payment {payment['payment_reference']} recorded successfully", status_code=201)
