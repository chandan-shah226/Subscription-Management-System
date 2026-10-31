"""
Invoice API Endpoints
=====================
Routes for invoice listing, automated generation from subscriptions, confirmation,
and cancellation.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from middleware.auth import api_response, api_error, get_current_user, prevent_customer_idor, roles_required
from services.invoice_service import InvoiceService

invoice_bp = Blueprint("invoices", __name__, url_prefix="/api/invoices")


@invoice_bp.route("", methods=["GET"])
@jwt_required()
def list_invoices():
    """Lists invoices. Customers see only their own invoices; staff/admin see all."""
    current_user = get_current_user()
    status_filter = request.args.get("status")
    search = request.args.get("search")
    customer_id = current_user.id if current_user.role == "customer" else request.args.get("customer_id", type=int)

    invoices = InvoiceService.list_invoices(customer_id=customer_id, status_filter=status_filter, search=search)
    return api_response(data=invoices, status_code=200)


@invoice_bp.route("/<int:invoice_id>", methods=["GET"])
@jwt_required()
def get_invoice(invoice_id):
    """Retrieves an invoice with line items and payment transactions."""
    current_user = get_current_user()
    inv = InvoiceService.get_invoice_by_id(invoice_id)
    if not inv:
        return api_error("Invoice not found", 404)

    if not prevent_customer_idor(inv["customer_id"], current_user):
        return api_error("Access forbidden: you can only view your own invoices", 403)

    return api_response(data=inv, status_code=200)


@invoice_bp.route("/generate/<int:subscription_id>", methods=["POST"])
@jwt_required()
def generate_from_subscription(subscription_id):
    """Generates an invoice from an active subscription."""
    current_user = get_current_user()
    data = request.get_json() or {}
    due_days = data.get("due_days", 15)
    discount_code = data.get("discount_code")

    invoice, error = InvoiceService.create_invoice_from_subscription(
        subscription_id=subscription_id,
        due_days=due_days,
        discount_code=discount_code
    )
    if error:
        return api_error(error, 400)
    return api_response(data=invoice, message=f"Invoice {invoice['invoice_number']} generated successfully", status_code=201)


@invoice_bp.route("/generate-batch", methods=["POST"])
@jwt_required()
@roles_required("admin", "staff")
def batch_generate_billing():
    """Billing day cron action: generates invoices for all due active subscriptions."""
    generated, count_due = InvoiceService.generate_all_due_invoices()
    return api_response(
        data={"generated": generated, "count": len(generated), "total_due": count_due},
        message=f"Billing day run complete: {len(generated)} invoices created.",
        status_code=200
    )


@invoice_bp.route("/<int:invoice_id>/confirm", methods=["POST"])
@jwt_required()
@roles_required("admin", "staff")
def confirm_invoice(invoice_id):
    """Confirms a draft invoice."""
    inv, error = InvoiceService.confirm_invoice(invoice_id)
    if error:
        return api_error(error, 400)
    return api_response(data=inv, message="Invoice confirmed successfully", status_code=200)


@invoice_bp.route("/<int:invoice_id>/cancel", methods=["POST"])
@jwt_required()
@roles_required("admin", "staff")
def cancel_invoice(invoice_id):
    """Cancels an invoice."""
    inv, error = InvoiceService.cancel_invoice(invoice_id)
    if error:
        return api_error(error, 400)
    return api_response(data=inv, message="Invoice cancelled successfully", status_code=200)


@invoice_bp.route("/<int:invoice_id>/send", methods=["POST"])
@jwt_required()
def send_invoice(invoice_id):
    """Simulates sending an invoice to customer's registered email."""
    inv = InvoiceService.get_invoice_by_id(invoice_id)
    if not inv:
        return api_error("Invoice not found", 404)
    return api_response(data=inv, message=f"Invoice {inv['invoice_number']} sent to {inv['customer_email']}", status_code=200)
