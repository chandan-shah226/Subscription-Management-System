"""
Razorpay Payment Gateway Service (Module 6)
===========================================
Official Razorpay Python SDK integration for:
1. Server-side Order Creation with accurate paise conversion.
2. Cryptographic HMAC-SHA256 Payment Signature Verification.
3. Cryptographic Webhook Signature Verification against raw request body.
4. Idempotent webhook event processing with duplicate suppression.
5. Strict customer isolation and server-authoritative amount validation.
"""

import hmac
import hashlib
import json
from decimal import Decimal
from datetime import datetime, date, timezone
from flask import current_app

import razorpay
from models import db, Invoice, Payment, PaymentWebhookEvent, User


def get_razorpay_client():
    """Instantiates the official Razorpay client using configured Test Mode keys."""
    key_id = current_app.config.get("RAZORPAY_KEY_ID", "rzp_test_placeholder_key")
    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET", "placeholder_secret")
    client = razorpay.Client(auth=(key_id, key_secret))
    return client


def create_order_for_invoice(invoice_id, customer_user):
    """
    Creates a Razorpay Order for the exact outstanding balance of a confirmed invoice.
    1. Validates invoice existence, Confirmed status, and customer ownership.
    2. Calculates amount in paise (1 INR = 100 paise) server-side.
    3. Calls official Razorpay SDK client.order.create.
    4. Creates a pending local payment attempt.
    """
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    # Customer boundary check
    if customer_user.role == "customer" and invoice.customer_id != customer_user.id:
        raise ValueError("Unauthorized: You do not own this invoice")

    if invoice.status != "Confirmed":
        raise ValueError(f"Only Confirmed invoices can be paid online. Current status is '{invoice.status}'")

    outstanding = invoice.outstanding_amount or Decimal("0.00")
    if outstanding <= Decimal("0.00"):
        raise ValueError("Invoice has no outstanding balance to pay")

    # Amount in smallest currency unit (paise)
    amount_in_paise = int((outstanding * Decimal("100.00")).quantize(Decimal("1")))

    key_id = current_app.config.get("RAZORPAY_KEY_ID")
    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET")

    # Check if mock mode is needed (for tests or missing keys)
    is_mock = (
        current_app.config.get("TESTING")
        or "placeholder" in str(key_id)
        or "replace" in str(key_id)
    )

    if is_mock:
        # Generate predictable mock order for testing and local exploration without internet
        mock_order_id = f"order_mock_{invoice.id}_{int(datetime.now().timestamp())}"
        order = {
            "id": mock_order_id,
            "entity": "order",
            "amount": amount_in_paise,
            "amount_paid": 0,
            "amount_due": amount_in_paise,
            "currency": "INR",
            "receipt": f"rcpt_{invoice.invoice_number}",
            "status": "created",
            "attempts": 0,
            "notes": {
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_id": invoice.customer_id
            }
        }
    else:
        try:
            client = get_razorpay_client()
            order_params = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": f"rcpt_{invoice.invoice_number}",
                "notes": {
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "customer_id": str(invoice.customer_id)
                }
            }
            order = client.order.create(data=order_params)
        except Exception as e:
            raise ValueError(f"Razorpay order creation failed: {str(e)}")

    # Record or update pending payment record
    payment_attempt = Payment.query.filter_by(
        invoice_id=invoice.id,
        status="pending",
        payment_source="razorpay"
    ).first()

    if not payment_attempt:
        payment_attempt = Payment(
            invoice_id=invoice.id,
            amount=outstanding,
            currency="INR",
            payment_method="Razorpay",
            payment_source="razorpay",
            status="pending",
            payment_date=date.today(),
            reference_number=order["id"],
            razorpay_order_id=order["id"],
            notes=f"Online payment initiated via Razorpay Order {order['id']}",
            created_by_id=customer_user.id
        )
        db.session.add(payment_attempt)
    else:
        payment_attempt.amount = outstanding
        payment_attempt.razorpay_order_id = order["id"]
        payment_attempt.reference_number = order["id"]
        payment_attempt.payment_date = date.today()

    db.session.commit()

    return {
        "order_id": order["id"],
        "amount": amount_in_paise,
        "currency": "INR",
        "key_id": key_id,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_name": invoice.customer.full_name if invoice.customer else "",
        "customer_email": invoice.customer.email if invoice.customer else "",
        "customer_phone": getattr(invoice.customer, "phone", "") or ""
    }


def verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Cryptographically verifies the Razorpay payment signature using HMAC-SHA256.
    Expected message: f"{razorpay_order_id}|{razorpay_payment_id}"
    """
    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return False

    key_secret = current_app.config.get("RAZORPAY_KEY_SECRET", "")
    expected_msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    generated_sig = hmac.new(
        key_secret.encode("utf-8"),
        expected_msg,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(generated_sig, razorpay_signature)


def verify_webhook_signature(raw_body_bytes, signature_header):
    """
    Verifies that incoming webhook requests originate from Razorpay using the Webhook Secret.
    """
    if not signature_header or not raw_body_bytes:
        return False

    webhook_secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return False

    generated_sig = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body_bytes,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(generated_sig, signature_header)


def process_payment_success(razorpay_order_id, razorpay_payment_id, razorpay_signature, current_user=None):
    """
    Completes checkout verification and settles the invoice:
    1. Cryptographically verifies HMAC signature.
    2. Finds pending payment attempt.
    3. Marks payment as captured.
    4. Updates invoice amount_paid, outstanding_amount, and resolves Paid status.
    """
    if not verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        raise ValueError("Invalid Razorpay payment signature. Verification failed.")

    # Locate payment attempt by order ID
    payment = Payment.query.filter_by(razorpay_order_id=razorpay_order_id).first()
    if not payment:
        raise ValueError(f"No payment record found matching Order ID '{razorpay_order_id}'")

    invoice = db.session.get(Invoice, payment.invoice_id)
    if not invoice:
        raise ValueError("Associated invoice not found")

    # Prevent double-processing
    if payment.status == "captured":
        return payment, invoice

    # Update payment record
    payment.status = "captured"
    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.payment_date = date.today()
    payment.notes = f"{payment.notes or ''}\nVerified online settlement captured: {razorpay_payment_id}".strip()

    # Reconcile invoice balances
    invoice.amount_paid = Decimal(str(invoice.amount_paid or 0)) + payment.amount
    invoice.outstanding_amount = max(Decimal("0.00"), Decimal(str(invoice.total_amount or 0)) - invoice.amount_paid)

    if invoice.outstanding_amount <= Decimal("0.00"):
        invoice.status = "Paid"

    invoice.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return payment, invoice


def process_webhook_event(raw_body_bytes, signature_header, event_id_header=None):
    """
    Secure, idempotent webhook receiver:
    1. Verifies raw body HMAC signature.
    2. Checks event_id against payment_webhook_events table to deduplicate.
    3. Handles payment.captured, payment.failed, order.paid safely.
    """
    if not verify_webhook_signature(raw_body_bytes, signature_header):
        raise ValueError("Invalid webhook signature")

    try:
        payload = json.loads(raw_body_bytes.decode("utf-8"))
    except Exception:
        raise ValueError("Malformed JSON webhook payload")

    event_id = event_id_header or payload.get("id") or f"evt_{hashlib.md5(raw_body_bytes).hexdigest()}"
    event_type = payload.get("event", "unknown")

    # Idempotency check
    existing_event = PaymentWebhookEvent.query.filter_by(event_id=event_id).first()
    if existing_event:
        return {"status": "skipped_duplicate", "event_id": event_id}

    # Record event
    webhook_log = PaymentWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        payload=json.dumps(payload),
        status="processed"
    )
    db.session.add(webhook_log)
    db.session.flush()

    # Process events
    if event_type in ["payment.captured", "order.paid"]:
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
        payment_id = payment_entity.get("id")
        amount_paise = payment_entity.get("amount", 0)
        captured_amount = Decimal(str(amount_paise)) / Decimal("100.00")

        if order_id:
            payment = Payment.query.filter_by(razorpay_order_id=order_id).first()
            if payment and payment.status != "captured":
                payment.status = "captured"
                payment.razorpay_payment_id = payment_id
                payment.amount = captured_amount

                inv = payment.invoice
                if inv:
                    inv.amount_paid = Decimal(str(inv.amount_paid or 0)) + captured_amount
                    inv.outstanding_amount = max(Decimal("0.00"), Decimal(str(inv.total_amount or 0)) - inv.amount_paid)
                    if inv.outstanding_amount <= Decimal("0.00"):
                        inv.status = "Paid"
                    inv.updated_at = datetime.now(timezone.utc)

    elif event_type == "payment.failed":
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
        if order_id:
            payment = Payment.query.filter_by(razorpay_order_id=order_id).first()
            # Do NOT downgrade if already captured
            if payment and payment.status != "captured":
                payment.status = "failed"
                payment.notes = f"{payment.notes or ''}\nGateway payment failed: {payment_entity.get('error_description')}".strip()

    db.session.commit()
    return {"status": "processed", "event_id": event_id, "event_type": event_type}
