"""
Payment API Routes (Module 6)
=============================
Unified Payment Management Blueprint.
Handles:
1. Role-scoped payment history and search with customer boundary isolation.
2. Dashboard KPI summary metrics.
3. Manual offline payment entry (Staff / Admin).
4. Razorpay online checkout order creation (paise conversion).
5. Razorpay HMAC-SHA256 callback signature verification & invoice settlement.
6. Cryptographic webhook receiver with raw payload verification & deduplication.
"""

from decimal import Decimal
from flask import Blueprint, request, jsonify

from middleware.auth_middleware import (
    get_current_user,
    auth_required,
    roles_required,
    verify_customer_access
)
from services.payment_service import (
    record_manual_payment,
    list_payments,
    get_payment_statistics
)
from services.razorpay_service import (
    create_order_for_invoice,
    process_payment_success,
    process_webhook_event
)
from models import db, Payment, Invoice

payment_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


@payment_bp.route("", methods=["GET"])
@auth_required
def get_payments():
    """
    Retrieves filtered and paginated payment records.
    Automatically scopes to customer's own invoices if caller has customer role.
    """
    current_user = get_current_user()
    filters = {
        "invoice_id": request.args.get("invoice_id"),
        "customer_id": request.args.get("customer_id"),
        "payment_method": request.args.get("payment_method"),
        "payment_source": request.args.get("payment_source"),
        "status": request.args.get("status"),
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
        "search": request.args.get("search", ""),
        "page": request.args.get("page", 1),
        "limit": request.args.get("limit", request.args.get("per_page", 20))
    }

    result = list_payments(filters, current_user=current_user)
    return jsonify({
        "success": True,
        "payments": result["payments"],
        "data": result["payments"],
        "pagination": result["pagination"]
    }), 200


@payment_bp.route("/stats", methods=["GET"])
@auth_required
def get_payment_stats():
    """Returns payment KPI statistics (scoped to customer if customer role)."""
    current_user = get_current_user()
    customer_id = current_user.id if current_user and current_user.role == "customer" else None
    if not customer_id and request.args.get("customer_id"):
        try:
            customer_id = int(request.args.get("customer_id"))
        except (ValueError, TypeError):
            pass

    stats = get_payment_statistics(customer_id=customer_id)
    return jsonify({
        "success": True,
        "stats": stats,
        "data": stats
    }), 200


@payment_bp.route("/<int:payment_id>", methods=["GET"])
@auth_required
def get_single_payment(payment_id):
    """Retrieves payment details with customer access validation."""
    payment = db.session.get(Payment, payment_id)
    if not payment:
        return jsonify({"success": False, "error": "Payment record not found"}), 404

    current_user = get_current_user()
    if payment.invoice and not verify_customer_access(payment.invoice, current_user):
        return jsonify({"success": False, "error": "Unauthorized access to payment record"}), 403

    p_dict = payment.to_dict()
    return jsonify({
        "success": True,
        "payment": p_dict,
        "data": p_dict
    }), 200


@payment_bp.route("/manual", methods=["POST"])
@roles_required("admin", "staff")
def record_offline_payment():
    """Staff/Admin manual offline payment recording (cash, bank transfer, cheque)."""
    data = request.get_json() or {}
    invoice_id = data.get("invoice_id")
    if not invoice_id:
        return jsonify({"success": False, "error": "invoice_id is required"}), 400

    current_user = get_current_user()
    try:
        payment, invoice = record_manual_payment(invoice_id, data, user=current_user)
        return jsonify({
            "success": True,
            "message": f"Payment of ₹{payment.amount:.2f} recorded successfully.",
            "payment": payment.to_dict(),
            "invoice": invoice.to_dict(include_items=False, include_payments=True)
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@payment_bp.route("/razorpay/create-order", methods=["POST"])
@auth_required
def razorpay_create_order():
    """
    Initiates Razorpay checkout order for the exact outstanding balance of a Confirmed invoice.
    Enforces customer ownership and calculates amount in paise.
    """
    data = request.get_json() or {}
    invoice_id = data.get("invoice_id")
    if not invoice_id:
        return jsonify({"success": False, "error": "invoice_id is required"}), 400

    current_user = get_current_user()
    try:
        order_details = create_order_for_invoice(invoice_id, customer_user=current_user)
        return jsonify({
            "success": True,
            "order": order_details
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@payment_bp.route("/razorpay/verify", methods=["POST"])
@auth_required
def razorpay_verify_payment():
    """
    Verifies the cryptographic HMAC-SHA256 signature from the Razorpay checkout callback.
    Transitions payment to 'captured' and settles invoice balance.
    """
    data = request.get_json() or {}
    order_id = data.get("razorpay_order_id")
    payment_id = data.get("razorpay_payment_id")
    signature = data.get("razorpay_signature")

    if not order_id or not payment_id or not signature:
        return jsonify({"success": False, "error": "Missing signature verification parameters"}), 400

    current_user = get_current_user()
    try:
        payment, invoice = process_payment_success(
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature,
            current_user=current_user
        )
        return jsonify({
            "success": True,
            "message": f"Payment {payment_id} successfully captured and invoice updated.",
            "payment": payment.to_dict(),
            "invoice": invoice.to_dict(include_items=False, include_payments=True)
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@payment_bp.route("/razorpay/webhook", methods=["POST"])
def razorpay_webhook():
    """
    Webhook receiver endpoint for asynchronous server-to-server notifications from Razorpay.
    Verifies raw payload HMAC against RAZORPAY_WEBHOOK_SECRET and deduplicates events.
    """
    raw_body = request.get_data()
    signature_header = request.headers.get("X-Razorpay-Signature", "")
    event_id_header = request.headers.get("X-Razorpay-Event-Id")

    if not signature_header:
        return jsonify({"error": "Missing X-Razorpay-Signature header"}), 400

    try:
        result = process_webhook_event(
            raw_body_bytes=raw_body,
            signature_header=signature_header,
            event_id_header=event_id_header
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
