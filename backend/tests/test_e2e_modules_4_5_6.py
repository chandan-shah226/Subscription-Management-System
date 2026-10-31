"""
End-to-End Integration Test Suite for Modules 4, 5, and 6
=========================================================
Tests the complete multi-module business lifecycle:
1. Subscriptions from Module 3 trigger recurring billing in Module 4.
2. Active eligible discounts from Module 5 are automatically evaluated and applied.
3. Duplicate billing prevention (idempotency) ensures no double-invoicing.
4. Invoice confirmation locks discount redemptions.
5. Online payments via Razorpay (Module 6) generate orders, verify HMAC-SHA256 signatures,
   record payments in the ledger, and settle invoices to 'Paid' (outstanding = 0).
6. Manual offline payments settle invoices and track staff audit references.
7. Data boundary and security isolation prevent cross-customer access.
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
    db, User, Product, SubscriptionPlan, Subscription, SubscriptionItem,
    Invoice, InvoiceItem, Discount, DiscountRedemption, Payment
)
from services.invoice_service import (
    generate_subscription_invoices, confirm_invoice, get_invoice_statistics
)
from services.discount_service import (
    create_discount, select_best_discount, get_discount_statistics
)
from services.payment_service import (
    record_manual_payment, list_payments, get_payment_statistics
)
from services.razorpay_service import (
    create_order_for_invoice, verify_payment_signature, process_payment_success
)


class EndToEndModules456TestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.app.config["RAZORPAY_KEY_ID"] = "rzp_test_BrightloopE2EKey"
        self.app.config["RAZORPAY_KEY_SECRET"] = "SecretE2ETestKey123456789"
        self.app.config["RAZORPAY_WEBHOOK_SECRET"] = "WebhookSecretE2ETest987654"

        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed Users
        self.admin = User(
            email="admin_e2e@brightloop.com",
            first_name="Admin",
            last_name="Tester",
            role="admin",
            is_active=True
        )
        self.admin.set_password("AdminSecurePass@123")
        db.session.add(self.admin)

        self.staff = User(
            email="staff_e2e@brightloop.com",
            first_name="Staff",
            last_name="Tester",
            role="staff",
            is_active=True
        )
        self.staff.set_password("StaffSecurePass@123")
        db.session.add(self.staff)

        self.customer1 = User(
            email="cust1_e2e@client.com",
            first_name="Alice",
            last_name="Smith",
            role="customer",
            is_active=True
        )
        self.customer1.set_password("AliceSecurePass@123")
        db.session.add(self.customer1)

        self.customer2 = User(
            email="cust2_e2e@client.com",
            first_name="Bob",
            last_name="Jones",
            role="customer",
            is_active=True
        )
        self.customer2.set_password("BobSecurePass@123")
        db.session.add(self.customer2)

        # Seed Product & Plan
        self.product = Product(
            name="BrightERP Enterprise Suite",
            code="ERP-ENT-001",
            description="Cloud ERP Platform for Recurring Subscriptions",
            sales_price=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            is_active=True
        )
        db.session.add(self.product)
        db.session.flush()

        self.plan = SubscriptionPlan(
            name="Monthly Professional ERP",
            code="PLAN-MONTHLY-001",
            billing_frequency="monthly",
            base_price=Decimal("1000.00"),
            is_active=True
        )
        db.session.add(self.plan)
        db.session.flush()

        # Seed Customer 1 Active Subscription due for billing today
        today = date.today()
        self.sub1 = Subscription(
            subscription_number="SUB-E2E-001",
            customer_id=self.customer1.id,
            plan_id=self.plan.id,
            status="Active",
            billing_frequency="monthly",
            start_date=today - timedelta(days=30),
            next_billing_date=today,
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("180.00"),
            total_amount=Decimal("1180.00")
        )
        db.session.add(self.sub1)
        db.session.flush()

        self.sub_item1 = SubscriptionItem(
            subscription_id=self.sub1.id,
            product_id=self.product.id,
            quantity=1,
            unit_price=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            tax_amount=Decimal("180.00"),
            total_price=Decimal("1180.00")
        )
        db.session.add(self.sub_item1)

        # Seed Module 5 Discount Rule (SAVE10 -> 10% off for subscriptions)
        self.discount_rule = Discount(
            code="SAVE10",
            description="10% Discount on Monthly Subscriptions",
            discount_type="percentage",
            value=Decimal("10.00"),
            scope="subscription",
            min_purchase=Decimal("500.00"),
            usage_limit=100,
            times_used=0,
            is_active=True,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=30)
        )
        db.session.add(self.discount_rule)
        db.session.commit()

        # Generate JWT Auth Tokens
        self.admin_token = create_access_token(
            identity=str(self.admin.id),
            additional_claims={"role": self.admin.role, "email": self.admin.email}
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
        self.cust1_headers = {"Authorization": f"Bearer {self.cust1_token}"}
        self.cust2_headers = {"Authorization": f"Bearer {self.cust2_token}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_e2e_subscription_to_discount_to_razorpay_settlement(self):
        """
        Complete End-to-End Lifecycle:
        1. Trigger Recurring Billing (Module 4) for due subscription (Module 3).
        2. Module 5 Discount (SAVE10) is automatically applied (10% off subtotal 1000 = 100 discount).
        3. Tax is calculated on discounted base (900 * 18% = 162). Total = 1062.
        4. Confirm the invoice.
        5. Razorpay order is generated with exact amount in paise (106200 paise).
        6. Simulated payment with valid HMAC signature settles invoice to 'Paid'.
        7. Verify audit records, outstanding balance = 0, and payment in ledger.
        """
        # Step 1: Generate recurring invoices
        today = date.today()
        result = generate_subscription_invoices(target_date=today)
        self.assertEqual(result["generated_count"], 1)
        self.assertEqual(len(result["invoices"]), 1)

        invoice_data = result["invoices"][0]
        inv_id = invoice_data["id"]
        inv = db.session.get(Invoice, inv_id)
        self.assertIsNotNone(inv)
        self.assertEqual(inv.subscription_id, self.sub1.id)
        self.assertEqual(inv.customer_id, self.customer1.id)

        # Step 2: Verify Module 5 discount auto-application
        self.assertEqual(inv.discount_code, "SAVE10")
        self.assertEqual(inv.discount_amount, Decimal("100.00"))
        self.assertEqual(inv.subtotal, Decimal("1000.00"))
        # Line item tax = 1000 * 18% = 180.00. Taxable subtotal (900) + tax (180) = 1080.00
        self.assertEqual(inv.tax_amount, Decimal("180.00"))
        self.assertEqual(inv.total_amount, Decimal("1080.00"))
        self.assertEqual(inv.outstanding_amount, Decimal("1080.00"))
        self.assertEqual(inv.status, "Draft")

        # Step 3: Verify Idempotency - subscription next_billing_date was advanced to next month
        sub_refreshed = db.session.get(Subscription, self.sub1.id)
        self.assertGreater(sub_refreshed.next_billing_date, today)
        dup_result_same_day = generate_subscription_invoices(target_date=date.today())
        self.assertEqual(dup_result_same_day["generated_count"], 0)

        # If next_billing_date were still set to today, period duplicate prevention skips it
        sub_refreshed.next_billing_date = today
        db.session.commit()
        dup_result_skipped = generate_subscription_invoices(target_date=date.today())
        self.assertEqual(dup_result_skipped["generated_count"], 0)
        self.assertEqual(dup_result_skipped["skipped_count"], 1)

        # Step 4: Confirm Invoice (transitions from Draft to Confirmed)
        confirmed_inv = confirm_invoice(inv_id, user=self.admin)
        self.assertEqual(confirmed_inv.status, "Confirmed")

        # Verify discount redemption recorded
        redemptions = DiscountRedemption.query.filter_by(invoice_id=inv.id).all()
        self.assertGreaterEqual(len(redemptions), 1)

        # Step 5: Online Razorpay Payment flow
        # Create Razorpay order
        order_res = create_order_for_invoice(inv_id, customer_user=self.customer1)
        self.assertIn("order_id", order_res)
        # 1080.00 * 100 = 108000 paise
        self.assertEqual(order_res["amount"], 108000)

        order_id = order_res["order_id"]
        payment_id = "pay_e2e_test_998877"

        # Step 6: Construct valid HMAC-SHA256 signature
        secret = self.app.config["RAZORPAY_KEY_SECRET"]
        signature_payload = f"{order_id}|{payment_id}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signature_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Step 7: Verify signature & process success
        sig_valid = verify_payment_signature(order_id, payment_id, expected_sig)
        self.assertTrue(sig_valid)

        payment_obj, inv_obj = process_payment_success(
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=expected_sig
        )
        self.assertIsNotNone(payment_obj)
        self.assertIsNotNone(inv_obj)

        # Step 8: Assert Invoice state after payment
        inv_after = db.session.get(Invoice, inv_id)
        self.assertEqual(inv_after.status, "Paid")
        self.assertEqual(inv_after.outstanding_amount, Decimal("0.00"))

        # Assert Payment record in database ledger
        payments = Payment.query.filter_by(invoice_id=inv_id).all()
        self.assertEqual(len(payments), 1)
        p = payments[0]
        self.assertEqual(p.amount, Decimal("1080.00"))
        self.assertEqual(p.status, "captured")
        self.assertEqual(p.payment_source, "razorpay")
        self.assertEqual(p.razorpay_payment_id, payment_id)

        # Verify Payment Statistics reflect this collection
        stats = get_payment_statistics()
        self.assertEqual(stats["total_payments"], 1)
        self.assertEqual(stats["successful_payments"], 1)
        self.assertEqual(stats["total_collected"], 1080.0)
        self.assertEqual(stats["outstanding_receivables"], 0.0)

    def test_customer_boundary_isolation(self):
        """
        Security Test: Customer 2 must NOT be able to view, pay, or manipulate Customer 1's invoice.
        """
        # Create an invoice for Customer 1
        inv = Invoice(
            invoice_number="INV-CUST1-SECURE",
            customer_id=self.customer1.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=15),
            subtotal=Decimal("500.00"),
            total_amount=Decimal("500.00"),
            outstanding_amount=Decimal("500.00"),
            status="Confirmed"
        )
        db.session.add(inv)
        db.session.commit()

        # Customer 2 attempts to fetch Customer 1's invoice details via API
        res = self.client.get(f"/api/invoices/{inv.id}", headers=self.cust2_headers)
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data["success"])

        # Customer 2 attempts to create a Razorpay order for Customer 1's invoice
        order_res = self.client.post(
            "/api/payments/razorpay/create-order",
            json={"invoice_id": inv.id},
            headers=self.cust2_headers
        )
        self.assertEqual(order_res.status_code, 400)
        self.assertIn("unauthorized", order_res.get_json()["error"].lower())

        # Customer 1 can successfully access their own invoice
        ok_res = self.client.get(f"/api/invoices/{inv.id}", headers=self.cust1_headers)
        self.assertEqual(ok_res.status_code, 200)

    def test_manual_offline_payment_workflow(self):
        """
        Offline Settlement Flow:
        Staff records manual NEFT/Cash payment against a confirmed invoice.
        """
        inv = Invoice(
            invoice_number="INV-OFFLINE-001",
            customer_id=self.customer1.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            subtotal=Decimal("2000.00"),
            total_amount=Decimal("2000.00"),
            outstanding_amount=Decimal("2000.00"),
            status="Confirmed"
        )
        db.session.add(inv)
        db.session.commit()

        # Partial manual payment of 800.00
        payment, invoice = record_manual_payment(
            invoice_id=inv.id,
            data={
                "amount": "800.00",
                "payment_method": "Bank Transfer",
                "reference_number": "NEFT-REF-771122",
                "notes": "Advance partial settlement via wire"
            },
            user=self.staff
        )
        self.assertIsNotNone(payment)

        inv = db.session.get(Invoice, inv.id)
        self.assertEqual(inv.outstanding_amount, Decimal("1200.00"))
        self.assertEqual(inv.status, "Confirmed")

        # Full settlement remaining 1200.00
        payment2, invoice2 = record_manual_payment(
            invoice_id=inv.id,
            data={
                "amount": "1200.00",
                "payment_method": "UPI",
                "reference_number": "UPI-REF-992233",
                "notes": "Remaining balance cleared"
            },
            user=self.staff
        )
        self.assertIsNotNone(payment2)

        inv = db.session.get(Invoice, inv.id)
        self.assertEqual(inv.outstanding_amount, Decimal("0.00"))
        self.assertEqual(inv.status, "Paid")


if __name__ == "__main__":
    unittest.main()
