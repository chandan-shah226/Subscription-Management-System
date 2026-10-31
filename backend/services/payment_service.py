"""
Payment Management Service
==========================
Handles recording incoming payments against invoices, updating receivable balances,
and transitioning invoices to paid status.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from models import db
from models.user import User
from models.invoice import Invoice
from models.payment import Payment


class PaymentService:
    """Service governing payment transaction records, payment matching, and invoice settlement."""

    @staticmethod
    def generate_payment_reference() -> str:
        """Generates sequential, unique payment references formatted as PAY-YYYY-XXXX."""
        year = datetime.now(timezone.utc).year
        prefix = f"PAY-{year}-"
        last_pay = Payment.query.filter(Payment.payment_reference.like(f"{prefix}%")).order_by(Payment.id.desc()).first()
        if last_pay and last_pay.payment_reference:
            try:
                seq = int(last_pay.payment_reference.split("-")[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @classmethod
    def list_payments(cls, customer_id: int | None = None, method: str | None = None, search: str | None = None):
        """Lists payment transactions with optional filters."""
        query = Payment.query

        if customer_id:
            query = query.filter_by(customer_id=customer_id)

        if method:
            query = query.filter_by(method=method.lower())

        if search:
            like = f"%{search.strip()}%"
            query = query.filter(
                (Payment.payment_reference.ilike(like)) |
                (Payment.customer.has(User.first_name.ilike(like))) |
                (Payment.customer.has(User.last_name.ilike(like))) |
                (Payment.note.ilike(like))
            )

        payments = query.order_by(Payment.id.desc()).all()
        return [p.to_dict() for p in payments]

    @classmethod
    def record_payment(cls, data: dict, user_id: int | None = None) -> tuple[dict | None, str | None]:
        """
        Records payment against an invoice and updates invoice status.
        """
        invoice_id = data.get("invoice_id")
        if not invoice_id:
            return None, "Field 'invoice_id' is required"

        invoice = db.session.get(Invoice, invoice_id)
        if not invoice:
            return None, "Invoice not found"

        if invoice.status == "cancelled":
            return None, "Cannot record payment against a cancelled invoice"

        try:
            amount = Decimal(str(data.get("amount", 0)))
            if amount <= Decimal("0.00"):
                return None, "Payment amount must be greater than zero"
        except Exception:
            return None, "Invalid payment amount"

        method = data.get("method", "card").lower()
        if method not in ["card", "bank_transfer", "cash", "upi"]:
            method = "card"

        paid_on_str = data.get("paid_on")
        if paid_on_str:
            try:
                paid_on = date.fromisoformat(paid_on_str)
            except ValueError:
                paid_on = date.today()
        else:
            paid_on = date.today()

        note = data.get("note", "").strip() or f"Payment received via {method.replace('_', ' ').capitalize()}"

        payment = Payment(
            payment_reference=cls.generate_payment_reference(),
            invoice_id=invoice.id,
            customer_id=invoice.customer_id,
            amount=amount,
            method=method,
            status="successful",
            paid_on=paid_on,
            note=note
        )
        db.session.add(payment)
        db.session.flush()

        # Check total paid amount on this invoice
        total_paid = Decimal("0.00")
        for p in invoice.payments.all():
            if p.status == "successful":
                total_paid += Decimal(str(p.amount))

        if total_paid >= Decimal(str(invoice.total_amount)):
            invoice.status = "paid"
        elif invoice.status == "draft":
            invoice.status = "confirmed"

        db.session.commit()
        return payment.to_dict(), None
