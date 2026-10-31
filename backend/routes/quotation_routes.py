"""
Quotation API Endpoints
=======================
Routes for quotation authoring, template management, calculations, and lifecycle transitions.
"""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from middleware.auth import api_response, api_error, get_current_user, roles_required, prevent_customer_idor
from services.quotation_service import QuotationService

quotation_bp = Blueprint("quotations", __name__, url_prefix="/api/quotations")


@quotation_bp.route("", methods=["GET"])
@jwt_required()
def list_quotations():
    """Lists quotations. Customers see only their own quotations; staff/admin see all."""
    current_user = get_current_user()
    status_filter = request.args.get("status")
    is_template = request.args.get("is_template", "false").lower() in ["true", "1"]

    customer_id = current_user.id if current_user.role == "customer" else request.args.get("customer_id", type=int)

    quotes = QuotationService.list_quotations(
        customer_id=customer_id,
        status_filter=status_filter,
        is_template=is_template
    )
    return api_response(data=quotes, status_code=200)


@quotation_bp.route("/templates", methods=["GET"])
@jwt_required()
def list_templates():
    """Lists reusable quotation templates."""
    templates = QuotationService.list_quotations(is_template=True)
    return api_response(data=templates, status_code=200)


@quotation_bp.route("/<int:quotation_id>", methods=["GET"])
@jwt_required()
def get_quotation(quotation_id):
    """Retrieves a quotation with line items and customer/plan details."""
    current_user = get_current_user()
    quotation = QuotationService.get_quotation_by_id(quotation_id)
    if not quotation:
        return api_error("Quotation not found", 404)

    # Customer IDOR prevention
    if not prevent_customer_idor(quotation["customer_id"], current_user):
        return api_error("Access forbidden: you can only view your own quotations", 403)

    return api_response(data=quotation, status_code=200)


@quotation_bp.route("", methods=["POST"])
@jwt_required()
def create_quotation():
    """Creates a new quotation with line items."""
    current_user = get_current_user()
    data = request.get_json() or {}

    # If customer creates quotation, enforce customer_id = current_user.id
    if current_user.role == "customer":
        data["customer_id"] = current_user.id

    quotation, error = QuotationService.create_quotation(data, creator_id=current_user.id)
    if error:
        return api_error(error, 400)
    return api_response(data=quotation, message="Quotation created successfully", status_code=201)


@quotation_bp.route("/<int:quotation_id>", methods=["PUT"])
@jwt_required()
def update_quotation(quotation_id):
    """Updates a draft quotation."""
    current_user = get_current_user()
    data = request.get_json() or {}

    quotation, error = QuotationService.update_quotation(
        quotation_id=quotation_id,
        data=data,
        user_id=current_user.id,
        user_role=current_user.role
    )
    if error:
        return api_error(error, 400)
    return api_response(data=quotation, message="Quotation updated successfully", status_code=200)


@quotation_bp.route("/<int:quotation_id>/send", methods=["POST"])
@jwt_required()
@roles_required("admin", "staff")
def send_quotation(quotation_id):
    """Marks a draft quotation as sent to the customer."""
    current_user = get_current_user()
    quotation, error = QuotationService.transition_status(quotation_id, "sent", current_user.id, current_user.role)
    if error:
        return api_error(error, 400)
    return api_response(data=quotation, message="Quotation sent successfully", status_code=200)


@quotation_bp.route("/<int:quotation_id>/confirm", methods=["POST"])
@jwt_required()
def confirm_quotation(quotation_id):
    """Confirms/accepts a quotation."""
    current_user = get_current_user()
    quotation, error = QuotationService.transition_status(quotation_id, "confirmed", current_user.id, current_user.role)
    if error:
        return api_error(error, 400)
    return api_response(data=quotation, message="Quotation confirmed successfully", status_code=200)


@quotation_bp.route("/<int:quotation_id>/reject", methods=["POST"])
@jwt_required()
def reject_quotation(quotation_id):
    """Rejects a quotation."""
    current_user = get_current_user()
    quotation, error = QuotationService.transition_status(quotation_id, "rejected", current_user.id, current_user.role)
    if error:
        return api_error(error, 400)
    return api_response(data=quotation, message="Quotation rejected", status_code=200)


@quotation_bp.route("/<int:quotation_id>/save-as-template", methods=["POST"])
@jwt_required()
@roles_required("admin", "staff")
def save_as_template(quotation_id):
    """Saves an existing quotation as a reusable template."""
    data = request.get_json() or {}
    template_name = data.get("template_name", "")
    template, error = QuotationService.save_as_template(quotation_id, template_name)
    if error:
        return api_error(error, 400)
    return api_response(data=template, message="Template saved successfully", status_code=201)

