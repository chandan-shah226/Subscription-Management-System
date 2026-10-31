"""
Invoice API Routes
==================
Module 4: Invoicing and Recurring Billing Blueprint.
Handles:
- Listing with search, multi-status filters, date range filters, sorting, and pagination
- Invoice KPI statistics / summary cards
- Invoice details retrieval with role boundary check
- Manual invoice creation and draft editing
- Status transitions: Confirm, Cancel, Payment recording
- Billing Day batch generation for due subscriptions
- Printable layout view
"""

from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, request, jsonify, render_template_string
from sqlalchemy import or_, desc, asc

from models import db, Invoice, InvoiceItem, Payment, User, Subscription
from middleware.auth_middleware import (
    get_current_user,
    auth_required,
    roles_required,
    verify_customer_access
)
from services.invoice_service import (
    create_invoice,
    update_invoice,
    confirm_invoice,
    cancel_invoice,
    record_payment,
    generate_subscription_invoices,
    get_invoice_statistics
)

invoice_bp = Blueprint("invoices", __name__, url_prefix="/api/invoices")


@invoice_bp.route("", methods=["GET"])
def list_invoices():
    """
    Retrieves paginated, filtered, and sorted invoices.
    Applies role-based scoping (customers only see their own).
    """
    current_user = get_current_user()
    query = Invoice.query.join(User, Invoice.customer_id == User.id)

    # Customer boundary check
    if current_user and current_user.role == "customer":
        query = query.filter(Invoice.customer_id == current_user.id)
    elif request.args.get("customer_id"):
        try:
            cid = int(request.args.get("customer_id"))
            query = query.filter(Invoice.customer_id == cid)
        except (ValueError, TypeError):
            pass

    # Search filter (Invoice number, customer name, email)
    search = request.args.get("search", "").strip()
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(search_fmt),
                User.first_name.ilike(search_fmt),
                User.last_name.ilike(search_fmt),
                (User.first_name + " " + User.last_name).ilike(search_fmt),
                User.email.ilike(search_fmt)
            )
        )

    # Status filter
    status = request.args.get("status", "").strip()
    if status and status.lower() != "all":
        if status.lower() == "overdue":
            today = date.today()
            query = query.filter(
                Invoice.status == "Confirmed",
                Invoice.outstanding_amount > 0,
                Invoice.due_date < today
            )
        else:
            query = query.filter(Invoice.status.ilike(status))

    # Date range filters (by invoice_date)
    start_date = request.args.get("start_date", "").strip()
    if start_date:
        try:
            s_date = date.fromisoformat(start_date)
            query = query.filter(Invoice.invoice_date >= s_date)
        except ValueError:
            pass

    end_date = request.args.get("end_date", "").strip()
    if end_date:
        try:
            e_date = date.fromisoformat(end_date)
            query = query.filter(Invoice.invoice_date <= e_date)
        except ValueError:
            pass

    # Subscription filter
    sub_id = request.args.get("subscription_id")
    if sub_id:
        try:
            query = query.filter(Invoice.subscription_id == int(sub_id))
        except (ValueError, TypeError):
            pass

    # Sorting
    sort_by = request.args.get("sort_by", "invoice_date")
    sort_dir = request.args.get("sort_dir", "desc").lower()

    sort_columns = {
        "invoice_number": Invoice.invoice_number,
        "invoice_date": Invoice.invoice_date,
        "due_date": Invoice.due_date,
        "total_amount": Invoice.total_amount,
        "amount_paid": Invoice.amount_paid,
        "outstanding_amount": Invoice.outstanding_amount,
        "status": Invoice.status,
        "customer": User.first_name,
        "created_at": Invoice.created_at
    }

    sort_col = sort_columns.get(sort_by, Invoice.invoice_date)
    if sort_dir == "asc":
        query = query.order_by(asc(sort_col), asc(Invoice.id))
    else:
        query = query.order_by(desc(sort_col), desc(Invoice.id))

    # Pagination
    try:
        page = max(1, int(request.args.get("page", 1)))
        limit_arg = request.args.get("per_page") or request.args.get("limit") or 20
        limit = min(100, max(1, int(limit_arg)))
    except (ValueError, TypeError):
        page = 1
        limit = 20

    total_records = query.count()
    invoices = query.offset((page - 1) * limit).limit(limit).all()

    total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1
    invoices_list = [inv.to_dict(include_items=False, include_payments=False) for inv in invoices]

    return jsonify({
        "success": True,
        "invoices": invoices_list,
        "data": invoices_list,
        "pagination": {
            "page": page,
            "limit": limit,
            "per_page": limit,
            "total": total_records,
            "total_records": total_records,
            "pages": total_pages,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }), 200


@invoice_bp.route("/stats", methods=["GET"])
def get_stats():
    """Returns invoice metrics for dashboard summary cards."""
    current_user = get_current_user()
    customer_id = None
    if current_user and current_user.role == "customer":
        customer_id = current_user.id
    elif request.args.get("customer_id"):
        try:
            customer_id = int(request.args.get("customer_id"))
        except (ValueError, TypeError):
            pass

    stats = get_invoice_statistics(customer_id)
    return jsonify({
        "success": True,
        "stats": stats,
        "data": stats
    }), 200


@invoice_bp.route("/<int:invoice_id>", methods=["GET"])
def get_invoice_detail(invoice_id):
    """Retrieves full invoice details with line items and payment logs."""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        return jsonify({"success": False, "error": "Invoice not found"}), 404

    current_user = get_current_user()
    if not verify_customer_access(invoice, current_user):
        return jsonify({"success": False, "error": "Unauthorized access to invoice"}), 403

    inv_dict = invoice.to_dict(include_items=True, include_payments=True)
    return jsonify({
        "success": True,
        "invoice": inv_dict,
        "data": inv_dict
    }), 200


@invoice_bp.route("", methods=["POST"])
@roles_required("admin", "staff")
def create_new_invoice():
    """Manual draft invoice creation by admin/staff."""
    data = request.get_json() or {}
    current_user = get_current_user()

    try:
        invoice = create_invoice(data, creator=current_user)
        return jsonify({
            "success": True,
            "message": f"Invoice {invoice.invoice_number} created successfully.",
            "invoice": invoice.to_dict(include_items=True, include_payments=False)
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@invoice_bp.route("/<int:invoice_id>", methods=["PUT"])
@roles_required("admin", "staff")
def update_draft_invoice(invoice_id):
    """Updates a draft invoice."""
    data = request.get_json() or {}
    current_user = get_current_user()

    try:
        invoice = update_invoice(invoice_id, data, user=current_user)
        return jsonify({
            "success": True,
            "message": f"Invoice {invoice.invoice_number} updated successfully.",
            "invoice": invoice.to_dict(include_items=True, include_payments=False)
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@invoice_bp.route("/<int:invoice_id>/confirm", methods=["POST"])
@roles_required("admin", "staff")
def confirm_invoice_endpoint(invoice_id):
    """Transitions invoice from Draft to Confirmed."""
    current_user = get_current_user()
    try:
        invoice = confirm_invoice(invoice_id, user=current_user)
        return jsonify({
            "success": True,
            "message": f"Invoice {invoice.invoice_number} confirmed.",
            "invoice": invoice.to_dict(include_items=True, include_payments=True)
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@invoice_bp.route("/<int:invoice_id>/cancel", methods=["POST"])
@roles_required("admin", "staff")
def cancel_invoice_endpoint(invoice_id):
    """Cancels an invoice."""
    data = request.get_json() or {}
    reason = data.get("reason", "Cancelled by administrator")
    current_user = get_current_user()

    try:
        invoice = cancel_invoice(invoice_id, reason=reason, user=current_user)
        return jsonify({
            "success": True,
            "message": f"Invoice {invoice.invoice_number} cancelled.",
            "invoice": invoice.to_dict(include_items=True, include_payments=True)
        }), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@invoice_bp.route("/<int:invoice_id>/payments", methods=["POST"])
def record_payment_endpoint(invoice_id):
    """Records payment for a confirmed invoice."""
    data = request.get_json() or {}
    current_user = get_current_user()

    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        return jsonify({"success": False, "error": "Invoice not found"}), 404

    if not verify_customer_access(invoice, current_user):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    try:
        payment, updated_invoice = record_payment(invoice_id, data, user=current_user)
        return jsonify({
            "success": True,
            "message": f"Payment of ₹{payment.amount:.2f} recorded successfully.",
            "payment": payment.to_dict(),
            "invoice": updated_invoice.to_dict(include_items=True, include_payments=True)
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@invoice_bp.route("/generate-recurring", methods=["POST"])
@roles_required("admin", "staff")
def generate_recurring_invoices_endpoint():
    """Triggers billing day batch generation for due subscriptions."""
    data = request.get_json() or {}
    target_date = data.get("target_date")
    result = generate_subscription_invoices(target_date)

    return jsonify({
        "success": True,
        "message": f"Billing engine finished: {result['generated_count']} invoices created, {result['skipped_count']} already up to date.",
        "result": result
    }), 200


@invoice_bp.route("/<int:invoice_id>/print", methods=["GET"])
def print_invoice(invoice_id):
    """Renders a clean printable invoice layout."""
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        return "Invoice not found", 404

    current_user = get_current_user()
    if not verify_customer_access(invoice, current_user):
        return "Unauthorized", 403

    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Invoice {{ invoice.invoice_number }} — Brightloop Software</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; color: #1e293b; background: #fff; }
            .header { display: flex; justify-content: space-between; border-bottom: 2px solid #714B67; padding-bottom: 20px; }
            .logo { font-size: 24px; font-weight: 700; color: #714B67; }
            .inv-meta { text-align: right; }
            .section { margin-top: 30px; display: flex; justify-content: space-between; }
            .bill-to h4 { margin: 0 0 8px 0; color: #64748b; text-transform: uppercase; font-size: 12px; }
            table { width: 100%; border-collapse: collapse; margin-top: 30px; }
            th { background: #f8fafc; text-align: left; padding: 12px; border-bottom: 2px solid #e2e8f0; color: #475569; }
            td { padding: 12px; border-bottom: 1px solid #e2e8f0; }
            .text-right { text-align: right; }
            .totals { width: 350px; margin-left: auto; margin-top: 20px; }
            .totals-row { display: flex; justify-content: space-between; padding: 6px 0; }
            .totals-row.grand { font-size: 18px; font-weight: 700; border-top: 2px solid #714B67; padding-top: 10px; color: #714B67; }
            .badge { display: inline-block; padding: 4px 10px; border-radius: 9999px; font-weight: 600; font-size: 12px; }
            .badge-draft { background: #f1f5f9; color: #475569; }
            .badge-confirmed { background: #e0f2fe; color: #0369a1; }
            .badge-paid { background: #dcfce7; color: #15803d; }
            .badge-cancelled { background: #fee2e2; color: #b91c1c; }
            .footer { margin-top: 50px; text-align: center; color: #94a3b8; font-size: 12px; border-top: 1px solid #e2e8f0; padding-top: 20px; }
            @media print { .no-print { display: none; } body { margin: 0; } }
        </style>
    </head>
    <body>
        <div class="no-print" style="margin-bottom: 20px;">
            <button onclick="window.print()" style="background:#714B67; color:#fff; border:none; padding:10px 20px; border-radius:6px; cursor:pointer; font-weight:600;">Print / Save as PDF</button>
        </div>

        <div class="header">
            <div>
                <div class="logo">Brightloop Software</div>
                <div style="color: #64748b; margin-top: 4px;">Subscription Management & Recurring Billing</div>
            </div>
            <div class="inv-meta">
                <h2 style="margin: 0; color: #714B67;">{{ invoice.invoice_number }}</h2>
                <div style="margin-top: 6px;">
                    <span class="badge badge-{{ invoice.status.lower() }}">{{ invoice.status.upper() }}</span>
                </div>
                <p style="margin: 6px 0 0 0; color: #64748b; font-size: 14px;">Date: {{ invoice.invoice_date }}</p>
                <p style="margin: 2px 0 0 0; color: #64748b; font-size: 14px;">Due Date: {{ invoice.due_date }}</p>
            </div>
        </div>

        <div class="section">
            <div class="bill-to">
                <h4>Billed To:</h4>
                <p style="margin: 0; font-weight: 600; font-size: 16px;">{{ invoice.customer.full_name }}</p>
                <p style="margin: 4px 0 0 0; color: #64748b;">{{ invoice.customer.email }}</p>
                {% if invoice.customer.phone %}
                <p style="margin: 2px 0 0 0; color: #64748b;">Phone: {{ invoice.customer.phone }}</p>
                {% endif %}
            </div>
            {% if invoice.subscription %}
            <div style="text-align: right;">
                <h4 style="margin: 0 0 8px 0; color: #64748b; text-transform: uppercase; font-size: 12px;">Subscription Ref:</h4>
                <p style="margin: 0; font-weight: 600;">{{ invoice.subscription.subscription_number }}</p>
                <p style="margin: 4px 0 0 0; color: #64748b; font-size: 13px;">Cycle: {{ invoice.subscription.billing_frequency.capitalize() }}</p>
            </div>
            {% endif %}
        </div>

        <table>
            <thead>
                <tr>
                    <th>Item Description</th>
                    <th class="text-right">Qty</th>
                    <th class="text-right">Unit Price (₹)</th>
                    <th class="text-right">Tax (18%)</th>
                    <th class="text-right">Total (₹)</th>
                </tr>
            </thead>
            <tbody>
                {% for item in invoice.items %}
                <tr>
                    <td>
                        <strong>{{ item.description }}</strong>
                        {% if item.variant %}
                        <div style="color: #64748b; font-size: 12px;">Variant: {{ item.variant.variant_name }}</div>
                        {% endif %}
                    </td>
                    <td class="text-right">{{ "%.2f"|format(item.quantity) }}</td>
                    <td class="text-right">{{ "%.2f"|format(item.unit_price) }}</td>
                    <td class="text-right">{{ "%.2f"|format(item.tax_amount) }}</td>
                    <td class="text-right" style="font-weight: 600;">{{ "%.2f"|format(item.total_amount) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="totals">
            <div class="totals-row">
                <span>Subtotal:</span>
                <span>₹{{ "%.2f"|format(invoice.subtotal) }}</span>
            </div>
            {% if invoice.discount_amount > 0 %}
            <div class="totals-row" style="color: #15803d;">
                <span>Discount:</span>
                <span>-₹{{ "%.2f"|format(invoice.discount_amount) }}</span>
            </div>
            {% endif %}
            <div class="totals-row">
                <span>Taxes:</span>
                <span>₹{{ "%.2f"|format(invoice.tax_amount) }}</span>
            </div>
            <div class="totals-row grand">
                <span>Total Amount:</span>
                <span>₹{{ "%.2f"|format(invoice.total_amount) }}</span>
            </div>
            <div class="totals-row" style="color: #15803d; margin-top: 4px;">
                <span>Amount Paid:</span>
                <span>₹{{ "%.2f"|format(invoice.amount_paid) }}</span>
            </div>
            <div class="totals-row" style="font-weight: 600; color: {% if invoice.outstanding_amount > 0 %}#b91c1c{% else %}#15803d{% endif %};">
                <span>Outstanding Balance:</span>
                <span>₹{{ "%.2f"|format(invoice.outstanding_amount) }}</span>
            </div>
        </div>

        {% if invoice.notes %}
        <div style="margin-top: 40px; padding: 15px; background: #f8fafc; border-radius: 8px; border-left: 4px solid #714B67;">
            <strong style="color: #475569; font-size: 13px;">Notes & Terms:</strong>
            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 13px;">{{ invoice.notes }}</p>
        </div>
        {% endif %}

        <div class="footer">
            <p>Thank you for your business! Brightloop Software — Automated Subscription Management.</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(template, invoice=invoice)
