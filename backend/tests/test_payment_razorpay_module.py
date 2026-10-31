"""
Test Suite for Module 6: Payment Management & Razorpay Integration
==================================================================
Comprehensive test coverage for:
1. Manual offline payment recording (Staff/Admin).
2. Partial manual payments & outstanding balance reconciliation.
3. Full manual payment transitions status to 'Paid'.
4. Overpayment prevention (rejection when payment > outstanding).
5. Customer boundary isolation (scoping & authorization).
6. Razorpay Test Mode order creation with exact paise calculation.
7. Cryptographic HMAC-SHA256 signature verification & forged signature rejection.
8. Online payment settlement and automated transition to 'Paid'.
9. Cryptographic raw-payload webhook signature verification.
10. Idempotent webhook deduplication via payment_webhook_events.
11. Webhook out-of-order protection (payment.failed does not overwrite captured).
12. Staff/Admin RBAC enforcement on manual payment recording.
"""

import sys
import os
import unittest
import hmac
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from flask_jwt_extended import create_access_token

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import (
    db, User, Invoice, InvoiceItem, Payment, PaymentWebhookEvent
)
from services.payment_service import (
    record_manual_payment, list_payments, get_payment_statistics
)
from services.razorpay_service import (
    create_order_for_invoice, verify_payment_signature, verify_webhook_signature,
    process_payment_success, process_webhook_event
)


class PaymentRazorpayModuleTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.app.config["RAZORPAY_KEY_ID"] = "rzp_test_BrightloopUnitTestKey"
        self.app.config["RAZORPAY_KEY_SECRET"] = "SecretUnitTestingKey12345"
        self.app.config["RAZORPAY_WEBHOOK_SECRET"] = "WebhookSecretTesting98765"

        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Admin
        self.admin = User(
            email="admin_pay@test.com",
            first_name="Admin",
            last_name="Pay",
            role="admin"
        )
        self.admin.set_password("AdminPass@123")
        db.session.add(self.admin)

        # Staff
        self.staff = User(
            email="staff_pay@test.com",
            first_name="Staff",
            last_name="Pay",
            role="staff"
        )
        self.staff.set_password("StaffPass@123")
        db.session.add(self.staff)

        # Customer 1
        self.customer1 = User(
            email="cust1_pay@test.com",
            first_name="Customer",
            last_name="One",
            role="customer"
        )
        self.customer1.set_password("CustOnePass@123")
        db.session.add(self.customer1)

        # Customer 2 (for isolation check)
        self.customer2 = User(
            email="cust2_pay@test.com",
            first_name="Customer",
            last_name="Two",
            role="customer"
        )
        self.customer2.set_password("CustTwoPass@123")
        db.session.add(self.customer2)
        db.session.commit()

        self.admin_token = create_access_token(
            identity=str(self.admin.id),
            additional_claims={"role": self.admin.role, "email": self.admin.email}
        )
        self.staff_token = create_access_token(
            identity=str(self.staff.id),
            additional_claims={"role": self.staff.role, "email": self.staff.email}
        )
        self.cust1_token = create_access_token(
            identity=str(self.customer1.id),
            additional_claims={"role": self.customer1.role, "email": self.customer1.email}
        )
        self.cust2_token = create_access_token(
            identity=str(self.customer2.id),
            additional_claims={"role": self.customer2.role, "email": self.customer2.email}
        )

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        self.cust1_headers = {"Authorization": f"Bearer {self.cust1_token}"}
        self.cust2_headers = {"Authorization": f"Bearer {self.cust2_token}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _create_sample_invoice(self, customer, total=Decimal("1180.00"), status="Confirmed"):
        inv = Invoice(
            invoice_number=f"INV-TEST-{int(total)}-{customer.id}",
            customer_id=customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=15),
            subtotal=total - Decimal("180.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("180.00"),
            total_amount=total,
            amount_paid=Decimal("0.00"),
            outstanding_amount=total,
            status=status
        )
        db.session.add(inv)
        db.session.flush()
        db.session.add(InvoiceItem(invoice_id=inv.id, description="Item", quantity=1, unit_price=total - Decimal("180.00"), total_amount=total))
        db.session.commit()
        return inv

    def test_manual_partial_and_full_payment_reconciliation(self):
        """Verifies partial manual payments reduce outstanding balance and full payment marks Paid."""
        inv = self._create_sample_invoice(self.customer1, total=Decimal("1000.00"))

        # Partial payment: 400
        pay1, inv = record_manual_payment(inv.id, {"amount": 400, "payment_method": "Bank Transfer"}, user=self.staff)
        self.assertEqual(inv.amount_paid, Decimal("400.00"))
        self.assertEqual(inv.outstanding_amount, Decimal("600.00"))
        self.assertEqual(inv.status, "Confirmed")

        # Full settlement: 600
        pay2, inv = record_manual_payment(inv.id, {"amount": 600, "payment_method": "Cash"}, user=self.admin)
        self.assertEqual(inv.amount_paid, Decimal("1000.00"))
        self.assertEqual(inv.outstanding_amount, Decimal("0.00"))
        self.assertEqual(inv.status, "Paid")

    def test_overpayment_prevention(self):
        """Verifies that paying more than the outstanding amount is strictly rejected."""
        inv = self._create_sample_invoice(self.customer1, total=Decimal("500.00"))

        with self.assertRaises(ValueError) as ctx:
            record_manual_payment(inv.id, {"amount": 550.00}, user=self.admin)
        self.assertIn("cannot exceed outstanding amount", str(ctx.exception))

    def test_customer_isolation_and_scoping(self):
        """Verifies customers cannot see other customers' payments or record manual payments."""
        inv1 = self._create_sample_invoice(self.customer1, total=Decimal("500.00"))
        inv2 = self._create_sample_invoice(self.customer2, total=Decimal("800.00"))

        record_manual_payment(inv1.id, {"amount": 200}, user=self.admin)
        record_manual_payment(inv2.id, {"amount": 300}, user=self.admin)

        # Customer 1 lists payments: should only see 1 payment
        res1 = self.client.get("/api/payments", headers=self.cust1_headers)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        self.assertEqual(len(data1["payments"]), 1)
        self.assertEqual(data1["payments"][0]["invoice_number"], inv1.invoice_number)

        # Customer 1 attempts manual payment route -> 403 Forbidden
        res_post = self.client.post("/api/payments/manual", json={"invoice_id": inv1.id, "amount": 100}, headers=self.cust1_headers)
        self.assertEqual(res_post.status_code, 403)

    def test_razorpay_order_creation_paise_conversion(self):
        """Verifies order creation calculates exact paise (e.g., ₹1250.50 -> 125050 paise)."""
        inv = self._create_sample_invoice(self.customer1, total=Decimal("1250.50"))

        order_data = create_order_for_invoice(inv.id, self.customer1)
        self.assertEqual(order_data["amount"], 125050)
        self.assertEqual(order_data["currency"], "INR")
        self.assertIn("order_", order_data["order_id"])

        # Pending payment record created
        pending = Payment.query.filter_by(razorpay_order_id=order_data["order_id"]).first()
        self.assertIsNotNone(pending)
        self.assertEqual(pending.status, "pending")
        self.assertEqual(pending.payment_source, "razorpay")

    def test_razorpay_signature_verification_and_settlement(self):
        """Verifies cryptographic HMAC signature check, rejecting forged signatures and settling valid ones."""
        inv = self._create_sample_invoice(self.customer1, total=Decimal("500.00"))
        order_data = create_order_for_invoice(inv.id, self.customer1)

        order_id = order_data["order_id"]
        payment_id = "pay_mock_success_778899"

        # Generate genuine HMAC signature
        key_secret = self.app.config["RAZORPAY_KEY_SECRET"]
        msg = f"{order_id}|{payment_id}".encode("utf-8")
        valid_sig = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        # 1. Test forged signature rejected
        forged_sig = "deadbeefcafebabe1234567890abcdef"
        with self.assertRaises(ValueError):
            process_payment_success(order_id, payment_id, forged_sig, self.customer1)

        # 2. Test valid signature processed
        payment, updated_inv = process_payment_success(order_id, payment_id, valid_sig, self.customer1)
        self.assertEqual(payment.status, "captured")
        self.assertEqual(payment.razorpay_payment_id, payment_id)
        self.assertEqual(updated_inv.status, "Paid")
        self.assertEqual(updated_inv.outstanding_amount, Decimal("0.00"))

    def test_webhook_cryptographic_verification_and_deduplication(self):
        """Verifies raw payload webhook signature check and idempotent deduplication."""
        inv = self._create_sample_invoice(self.customer1, total=Decimal("800.00"))
        order_data = create_order_for_invoice(inv.id, self.customer1)

        webhook_secret = self.app.config["RAZORPAY_WEBHOOK_SECRET"]
        payload_dict = {
            "entity": "event",
            "account_id": "acc_test",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_hook_112233",
                        "order_id": order_data["order_id"],
                        "amount": 80000,
                        "status": "captured"
                    }
                }
            }
        }
        raw_body = json.dumps(payload_dict).encode("utf-8")
        valid_hook_sig = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

        # Send webhook
        res = self.client.post(
            "/api/payments/razorpay/webhook",
            data=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": valid_hook_sig,
                "X-Razorpay-Event-Id": "evt_unique_12345"
            }
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "processed")

        # Verify payment captured and invoice paid
        inv_check = db.session.get(Invoice, inv.id)
        self.assertEqual(inv_check.status, "Paid")
        self.assertEqual(inv_check.amount_paid, Decimal("800.00"))

        # Re-send identical webhook (idempotency test)
        res_dup = self.client.post(
            "/api/payments/razorpay/webhook",
            data=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": valid_hook_sig,
                "X-Razorpay-Event-Id": "evt_unique_12345"
            }
        )
        self.assertEqual(res_dup.status_code, 200)
        data_dup = res_dup.get_json()
        self.assertEqual(data_dup["status"], "skipped_duplicate")

    def test_webhook_out_of_order_protection(self):
        """Verifies late payment.failed webhook does not downgrade an already captured payment."""
        inv = self._create_sample_invoice(self.customer1, total=Decimal("500.00"))
        order_data = create_order_for_invoice(inv.id, self.customer1)

        payment = Payment.query.filter_by(razorpay_order_id=order_data["order_id"]).first()
        payment.status = "captured"
        inv.status = "Paid"
        inv.amount_paid = Decimal("500.00")
        inv.outstanding_amount = Decimal("0.00")
        db.session.commit()

        # Now simulate late arriving payment.failed event
        webhook_secret = self.app.config["RAZORPAY_WEBHOOK_SECRET"]
        failed_payload = {
            "event": "payment.failed",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_hook_failed_99",
                        "order_id": order_data["order_id"],
                        "error_description": "Network timeout"
                    }
                }
            }
        }
        raw_body = json.dumps(failed_payload).encode("utf-8")
        sig = hmac.new(webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

        res = self.client.post(
            "/api/payments/razorpay/webhook",
            data=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": sig,
                "X-Razorpay-Event-Id": "evt_late_failure"
            }
        )
        self.assertEqual(res.status_code, 200)

        # Confirm payment is STILL captured and invoice is STILL Paid
        reloaded_payment = db.session.get(Payment, payment.id)
        self.assertEqual(reloaded_payment.status, "captured")
        reloaded_inv = db.session.get(Invoice, inv.id)
        self.assertEqual(reloaded_inv.status, "Paid")


if __name__ == "__main__":
    unittest.main()
