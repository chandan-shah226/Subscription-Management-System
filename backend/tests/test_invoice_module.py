"""
Comprehensive Test Suite for Module 4: Invoice Management
==========================================================
Verifies all 14 backend verification requirements specified in Phase 7:
1. Invoice listing and pagination
2. Invoice search and filtering
3. Invoice creation with valid data
4. Rejection of invalid invoice data
5. Correct subtotal, discount, tax, and total calculations
6. Unique invoice number generation
7. Draft editing restrictions
8. Valid and invalid status transitions
9. Unauthorized invoice access & role scoping
10. Customer and subscription relationship validation
11. Duplicate recurring invoice prevention
12. Safe retry of scheduled billing
13. Payment and outstanding balance consistency
14. Printable / PDF-ready view generation
"""

import sys
import os
import unittest
from datetime import date, timedelta
from decimal import Decimal

# Ensure backend root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import (
    db, User, Product, SubscriptionPlan, Subscription, SubscriptionItem,
    Invoice, InvoiceItem, Payment, Discount
)
from services.invoice_service import (
    quantize_money,
    generate_unique_invoice_number,
    compute_invoice_totals,
    create_invoice,
    update_invoice,
    confirm_invoice,
    cancel_invoice,
    record_payment,
    generate_subscription_invoices,
    get_invoice_statistics
)


class InvoiceModuleTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Seed test actors
        self.admin = User(
            email="admin@test.com",
            first_name="Admin",
            last_name="User",
            role="admin"
        )
        self.admin.set_password("Admin@123")

        self.staff = User(
            email="staff@test.com",
            first_name="Staff",
            last_name="User",
            role="staff"
        )
        self.staff.set_password("Staff@123")

        self.customer1 = User(
            email="cust1@test.com",
            first_name="Alice",
            last_name="Customer",
            role="customer"
        )
        self.customer1.set_password("Cust@123")

        self.customer2 = User(
            email="cust2@test.com",
            first_name="Bob",
            last_name="Customer",
            role="customer"
        )
        self.customer2.set_password("Cust@123")

        db.session.add_all([self.admin, self.staff, self.customer1, self.customer2])
        db.session.commit()

        # Seed test product & plan
        self.product = Product(
            name="SaaS License",
            code="PROD-SAAS",
            sales_price=Decimal("1000.00"),
            cost_price=Decimal("200.00"),
            tax_rate=Decimal("18.00")
        )
        self.plan = SubscriptionPlan(
            name="Monthly Plan",
            code="PLAN-MONTHLY",
            billing_frequency="monthly",
            base_price=Decimal("1000.00")
        )
        db.session.add_all([self.product, self.plan])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_invoice_creation_with_valid_data(self):
        """Verifies invoice creation with valid line items and metadata."""
        data = {
            "customer_id": self.customer1.id,
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=15)).isoformat(),
            "items": [
                {
                    "product_id": self.product.id,
                    "description": "Standard User Seat",
                    "quantity": 2,
                    "unit_price": 1000.00,
                    "tax_rate": 18.00,
                    "discount_amount": 100.00
                }
            ],
            "notes": "Thank you for subscribing."
        }
        invoice = create_invoice(data, self.admin)
        self.assertIsNotNone(invoice.id)
        self.assertTrue(invoice.invoice_number.startswith(f"INV-{date.today().year}-"))
        self.assertEqual(invoice.status, "Draft")
        self.assertEqual(invoice.customer_id, self.customer1.id)
        self.assertEqual(invoice.subtotal, Decimal("2000.00"))
        self.assertEqual(invoice.discount_amount, Decimal("100.00"))
        # Taxable: 2000 - 100 = 1900. Tax: 1900 * 18% = 342. Total: 2242.00
        self.assertEqual(invoice.tax_amount, Decimal("342.00"))
        self.assertEqual(invoice.total_amount, Decimal("2242.00"))
        self.assertEqual(invoice.outstanding_amount, Decimal("2242.00"))
        self.assertEqual(invoice.amount_paid, Decimal("0.00"))

    def test_rejection_of_invalid_invoice_data(self):
        """Verifies strict validation: due date before invoice date, missing customer, empty items."""
        # 1. Nonexistent customer
        with self.assertRaises(ValueError) as ctx:
            create_invoice({
                "customer_id": 9999,
                "items": [{"description": "Item", "quantity": 1, "unit_price": 50}]
            })
        self.assertIn("does not exist", str(ctx.exception))

        # 2. Empty line items
        with self.assertRaises(ValueError) as ctx:
            create_invoice({
                "customer_id": self.customer1.id,
                "items": []
            })
        self.assertIn("at least one line item", str(ctx.exception))

        # 3. Due date precedes invoice date
        with self.assertRaises(ValueError) as ctx:
            create_invoice({
                "customer_id": self.customer1.id,
                "invoice_date": date.today().isoformat(),
                "due_date": (date.today() - timedelta(days=1)).isoformat(),
                "items": [{"description": "Item", "quantity": 1, "unit_price": 50}]
            })
        self.assertIn("cannot precede", str(ctx.exception))

    def test_correct_financial_calculations(self):
        """Verifies subtotal, discount, tax, and final amount calculation flow."""
        items = [
            {"description": "Item 1", "quantity": 3, "unit_price": 500, "tax_rate": 10, "discount_amount": 50},
            {"description": "Item 2", "quantity": 2, "unit_price": 750, "tax_rate": 20, "discount_amount": 0}
        ]
        # Item 1: sub = 1500, disc = 50, taxable = 1450, tax = 145.00, tot = 1595.00
        # Item 2: sub = 1500, disc = 0, taxable = 1500, tax = 300.00, tot = 1800.00
        # Overall subtotal = 3000.00, Total tax = 445.00
        financials = compute_invoice_totals(items, overall_discount=Decimal("100.00"))
        self.assertEqual(financials["subtotal"], Decimal("3000.00"))
        self.assertEqual(financials["discount_amount"], Decimal("150.00")) # 50 line + 100 overall
        self.assertEqual(financials["tax_amount"], Decimal("445.00"))
        # Taxable: 3000 - 150 = 2850. Final: 2850 + 445 = 3295.00
        self.assertEqual(financials["total_amount"], Decimal("3295.00"))

    def test_unique_invoice_number_generation(self):
        """Verifies unique, formatted invoice numbering without collision."""
        num1 = generate_unique_invoice_number()
        inv1 = Invoice(
            invoice_number=num1, customer_id=self.customer1.id,
            invoice_date=date.today(), due_date=date.today() + timedelta(days=15),
            total_amount=Decimal("100.00"), outstanding_amount=Decimal("100.00")
        )
        db.session.add(inv1)
        db.session.commit()

        num2 = generate_unique_invoice_number()
        self.assertNotEqual(num1, num2)
        self.assertTrue(num2.startswith(f"INV-{date.today().year}-"))

    def test_draft_editing_restrictions(self):
        """Verifies Draft invoices can be updated, but Confirmed invoices reject editing."""
        invoice = create_invoice({
            "customer_id": self.customer1.id,
            "items": [{"description": "Line", "quantity": 1, "unit_price": 500}]
        })
        self.assertEqual(invoice.status, "Draft")

        # Edit draft
        updated = update_invoice(invoice.id, {
            "notes": "Updated note",
            "items": [{"description": "Line modified", "quantity": 2, "unit_price": 600}]
        })
        self.assertEqual(updated.total_amount, Decimal("1200.00"))
        self.assertEqual(updated.notes, "Updated note")

        # Confirm invoice
        confirm_invoice(invoice.id)
        self.assertEqual(invoice.status, "Confirmed")

        # Editing Confirmed invoice must fail
        with self.assertRaises(ValueError) as ctx:
            update_invoice(invoice.id, {"notes": "Forbidden edit"})
        self.assertIn("Only Draft invoices may be modified", str(ctx.exception))

    def test_status_workflow_transitions(self):
        """Verifies Draft -> Confirmed -> Paid, and invalid transitions."""
        invoice = create_invoice({
            "customer_id": self.customer1.id,
            "items": [{"description": "Service", "quantity": 1, "unit_price": 1000}]
        })
        # Cannot pay a Draft invoice directly
        with self.assertRaises(ValueError) as ctx:
            record_payment(invoice.id, {"amount": 500})
        self.assertIn("Draft invoice", str(ctx.exception))

        # Confirm
        confirm_invoice(invoice.id)
        self.assertEqual(invoice.status, "Confirmed")

        # Record payment
        payment, inv = record_payment(invoice.id, {"amount": 1000, "payment_method": "UPI"})
        self.assertEqual(inv.status, "Paid")
        self.assertEqual(inv.outstanding_amount, Decimal("0.00"))
        self.assertEqual(inv.amount_paid, Decimal("1000.00"))

        # Cannot cancel a Paid invoice with payments
        with self.assertRaises(ValueError) as ctx:
            cancel_invoice(invoice.id)
        self.assertIn("payments have been recorded", str(ctx.exception))

    def test_customer_subscription_relationship_validation(self):
        """Verifies invoices reject subscriptions belonging to a different customer."""
        sub_bob = Subscription(
            subscription_number="SUB-BOB-001",
            customer_id=self.customer2.id,
            plan_id=self.plan.id,
            status="Active",
            start_date=date.today(),
            next_billing_date=date.today()
        )
        db.session.add(sub_bob)
        db.session.commit()

        # Try to link Alice's invoice to Bob's subscription
        with self.assertRaises(ValueError) as ctx:
            create_invoice({
                "customer_id": self.customer1.id,
                "subscription_id": sub_bob.id,
                "items": [{"description": "Item", "quantity": 1, "unit_price": 100}]
            })
        self.assertIn("does not belong to customer", str(ctx.exception))

    def test_duplicate_recurring_billing_prevention(self):
        """Verifies Billing Day generates invoices once and avoids duplicates on retry."""
        sub = Subscription(
            subscription_number="SUB-REC-001",
            customer_id=self.customer1.id,
            plan_id=self.plan.id,
            status="Active",
            billing_frequency="monthly",
            start_date=date.today() - timedelta(days=30),
            next_billing_date=date.today()
        )
        db.session.add(sub)
        db.session.flush()

        line = SubscriptionItem(
            subscription_id=sub.id,
            product_id=self.product.id,
            quantity=1,
            unit_price=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            tax_amount=Decimal("180.00"),
            total_price=Decimal("1180.00")
        )
        db.session.add(line)
        db.session.commit()

        # Run 1
        run1 = generate_subscription_invoices(target_date=date.today())
        self.assertEqual(run1["generated_count"], 1)
        self.assertEqual(run1["skipped_count"], 0)

        # Verify next_billing_date moved to next month
        sub_refreshed = db.session.get(Subscription, sub.id)
        self.assertGreater(sub_refreshed.next_billing_date, date.today())

        # Run 2 immediately (safe retry)
        run2 = generate_subscription_invoices(target_date=date.today())
        self.assertEqual(run2["generated_count"], 0)
        self.assertEqual(run2["skipped_count"], 0)

    def test_payment_and_outstanding_balance_consistency(self):
        """Verifies partial and full payments keep outstanding balance strictly synchronized."""
        invoice = create_invoice({
            "customer_id": self.customer1.id,
            "items": [{"description": "Item", "quantity": 1, "unit_price": 2000}]
        })
        confirm_invoice(invoice.id)

        # Partial Payment
        pay1, inv = record_payment(invoice.id, {"amount": 800, "payment_method": "Credit Card"})
        self.assertEqual(inv.status, "Confirmed")
        self.assertEqual(inv.amount_paid, Decimal("800.00"))
        self.assertEqual(inv.outstanding_amount, Decimal("1200.00"))

        # Overpayment must fail
        with self.assertRaises(ValueError) as ctx:
            record_payment(invoice.id, {"amount": 1500})
        self.assertIn("cannot exceed", str(ctx.exception))

        # Final Payment
        pay2, inv = record_payment(invoice.id, {"amount": 1200, "payment_method": "Bank Transfer"})
        self.assertEqual(inv.status, "Paid")
        self.assertEqual(inv.amount_paid, Decimal("2000.00"))
        self.assertEqual(inv.outstanding_amount, Decimal("0.00"))

    def test_customer_isolation_and_api_scoping(self):
        """Verifies API endpoints enforce customer boundaries."""
        inv_alice = create_invoice({
            "customer_id": self.customer1.id,
            "items": [{"description": "Alice Item", "quantity": 1, "unit_price": 500}]
        })

        # Alice requests her invoice -> Allowed
        res = self.client.get(
            f"/api/invoices/{inv_alice.id}",
            headers={"X-Demo-User": self.customer1.email}
        )
        self.assertEqual(res.status_code, 200)

        # Bob requests Alice's invoice -> Forbidden (403)
        res = self.client.get(
            f"/api/invoices/{inv_alice.id}",
            headers={"X-Demo-User": self.customer2.email}
        )
        self.assertEqual(res.status_code, 403)

        # Customer listing invoices -> Only returns their own
        res = self.client.get(
            "/api/invoices",
            headers={"X-Demo-User": self.customer1.email}
        )
        data = res.get_json()
        self.assertEqual(data["pagination"]["total"], 1)

    def test_search_filtering_and_pagination(self):
        """Verifies search, status filtering, and pagination on /api/invoices."""
        for i in range(5):
            create_invoice({
                "customer_id": self.customer1.id,
                "items": [{"description": f"Item {i}", "quantity": 1, "unit_price": 100 * (i + 1)}]
            })

        # Pagination: per_page=2, page=1
        res = self.client.get("/api/invoices?page=1&per_page=2")
        data = res.get_json()
        self.assertEqual(len(data["invoices"]), 2)
        self.assertEqual(data["pagination"]["total"], 5)
        self.assertEqual(data["pagination"]["pages"], 3)

        # Filter by status
        res_draft = self.client.get("/api/invoices?status=Draft")
        self.assertEqual(res_draft.get_json()["pagination"]["total"], 5)

        res_paid = self.client.get("/api/invoices?status=Paid")
        self.assertEqual(res_paid.get_json()["pagination"]["total"], 0)

    def test_invoice_summary_statistics(self):
        """Verifies aggregate KPI numbers for dashboard."""
        inv1 = create_invoice({
            "customer_id": self.customer1.id,
            "items": [{"description": "Item", "quantity": 1, "unit_price": 1000}]
        })
        confirm_invoice(inv1.id)
        record_payment(inv1.id, {"amount": 1000})

        inv2 = create_invoice({
            "customer_id": self.customer1.id,
            "items": [{"description": "Item", "quantity": 1, "unit_price": 500}]
        })

        stats = get_invoice_statistics()
        self.assertEqual(stats["total_invoices"]["count"], 2)
        self.assertEqual(stats["paid_invoices"]["count"], 1)
        self.assertEqual(stats["draft_invoices"]["count"], 1)
        self.assertEqual(stats["total_collected"], 1000.00)

    def test_print_layout_endpoint(self):
        """Verifies /api/invoices/<id>/print returns printer-ready HTML."""
        inv = create_invoice({
            "customer_id": self.customer1.id,
            "items": [{"description": "Printable Line", "quantity": 1, "unit_price": 500}]
        })
        res = self.client.get(f"/api/invoices/{inv.id}/print")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Brightloop Software", res.get_data(as_text=True))
        self.assertIn(inv.invoice_number, res.get_data(as_text=True))

    def test_api_full_invoice_lifecycle_endpoints(self):
        """Verifies complete end-to-end API lifecycle: create -> update -> confirm -> pay."""
        payload = {
            "customer_id": self.customer1.id,
            "invoice_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=15)).isoformat(),
            "items": [
                {"description": "Consulting Block", "quantity": 5, "unit_price": 200, "tax_rate": 18}
            ]
        }
        res_create = self.client.post(
            "/api/invoices",
            json=payload,
            headers={"X-Demo-User": self.admin.email}
        )
        self.assertEqual(res_create.status_code, 201)
        inv_data = res_create.get_json()["invoice"]
        inv_id = inv_data["id"]
        self.assertEqual(inv_data["status"], "Draft")

        # Update via API
        update_payload = {
            "notes": "Updated project notes",
            "items": [
                {"description": "Consulting Block Revised", "quantity": 6, "unit_price": 200, "tax_rate": 18}
            ]
        }
        res_update = self.client.put(
            f"/api/invoices/{inv_id}",
            json=update_payload,
            headers={"X-Demo-User": self.admin.email}
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.get_json()["invoice"]["subtotal"], 1200.00)

        # Confirm via API
        res_confirm = self.client.post(
            f"/api/invoices/{inv_id}/confirm",
            headers={"X-Demo-User": self.admin.email}
        )
        self.assertEqual(res_confirm.status_code, 200)
        self.assertEqual(res_confirm.get_json()["invoice"]["status"], "Confirmed")

        # Pay via API
        total = res_confirm.get_json()["invoice"]["total_amount"]
        res_pay = self.client.post(
            f"/api/invoices/{inv_id}/payments",
            json={"amount": total, "payment_method": "Bank Transfer"},
            headers={"X-Demo-User": self.staff.email}
        )
        self.assertEqual(res_pay.status_code, 201)
        self.assertEqual(res_pay.get_json()["invoice"]["status"], "Paid")
        self.assertEqual(res_pay.get_json()["invoice"]["outstanding_amount"], 0.00)

    def test_api_billing_day_batch_endpoint(self):
        """Verifies POST /api/invoices/generate-recurring batch execution."""
        sub = Subscription(
            subscription_number="SUB-API-001",
            customer_id=self.customer2.id,
            plan_id=self.plan.id,
            status="Active",
            billing_frequency="monthly",
            start_date=date.today() - timedelta(days=30),
            next_billing_date=date.today()
        )
        db.session.add(sub)
        db.session.commit()

        res = self.client.post(
            "/api/invoices/generate-recurring",
            json={"target_date": date.today().isoformat()},
            headers={"X-Demo-User": self.admin.email}
        )
        self.assertEqual(res.status_code, 200)
        result = res.get_json()["result"]
        self.assertEqual(result["generated_count"], 1)


if __name__ == "__main__":
    unittest.main()
