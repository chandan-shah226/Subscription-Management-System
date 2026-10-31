"""
Product and Variant Management Service
======================================
Handles catalog operations, variant pricing calculations, SKU uniqueness,
and validation of product availability.
"""

from decimal import Decimal
from models import db
from models.product import Product, ProductVariant


class ProductService:
    """Service handling Product and Variant operations."""

    @staticmethod
    def list_products(active_only: bool = False, product_type: str | None = None, search: str | None = None):
        """Lists products with optional filtering."""
        query = Product.query

        if active_only:
            query = query.filter_by(is_active=True)
        if product_type:
            query = query.filter_by(product_type=product_type)
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter((Product.name.ilike(term)) | (Product.code.ilike(term)))

        return [product.to_dict(include_variants=True) for product in query.order_by(Product.name.asc()).all()]

    @staticmethod
    def get_product_by_id(product_id: int):
        """Retrieves a single product with variants."""
        product = db.session.get(Product, product_id)
        return product.to_dict(include_variants=True) if product else None

    @classmethod
    def create_product(cls, data: dict) -> tuple[dict | None, str | None]:
        """Creates a new product with validation."""
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip().upper()
        product_type = (data.get("product_type") or "service").strip().lower()
        description = (data.get("description") or "").strip() or None
        notes = (data.get("notes") or "").strip() or None

        if not name or not code:
            return None, "Product name and unique code are required"

        try:
            sales_price = Decimal(str(data.get("sales_price", 0)))
            cost_price = Decimal(str(data.get("cost_price", 0)))
            tax_rate = Decimal(str(data.get("tax_rate", 18.00)))
        except Exception:
            return None, "Sales price, cost price, and tax rate must be valid numbers"

        if sales_price < 0 or cost_price < 0 or tax_rate < 0:
            return None, "Prices and tax rate cannot be negative"

        if Product.query.filter_by(code=code).first():
            return None, f"Product code '{code}' already exists"

        product = Product(
            name=name,
            code=code,
            description=description,
            product_type=product_type,
            sales_price=sales_price,
            cost_price=cost_price,
            tax_rate=tax_rate,
            notes=notes,
            is_active=bool(data.get("is_active", True)),
        )
        db.session.add(product)
        db.session.flush()

        # Handle initial variants if supplied
        variants_data = data.get("variants", [])
        for v in variants_data:
            v_name = (v.get("variant_name") or "").strip()
            v_sku = (v.get("sku") or "").strip().upper()
            if not v_name or not v_sku:
                continue
            v_add_price = Decimal(str(v.get("additional_price", 0)))
            if v_add_price < 0:
                v_add_price = Decimal("0.00")
            if ProductVariant.query.filter_by(sku=v_sku).first():
                db.session.rollback()
                return None, f"Variant SKU '{v_sku}' already exists"

            variant = ProductVariant(
                product_id=product.id,
                variant_name=v_name,
                sku=v_sku,
                additional_price=v_add_price,
                is_active=bool(v.get("is_active", True)),
            )
            db.session.add(variant)

        db.session.commit()
        return product.to_dict(include_variants=True), None

    @classmethod
    def update_product(cls, product_id: int, data: dict) -> tuple[dict | None, str | None]:
        """Updates an existing product while preserving historical data."""
        product = db.session.get(Product, product_id)
        if not product:
            return None, "Product not found"

        if "name" in data and data["name"].strip():
            product.name = data["name"].strip()

        if "code" in data:
            code = data["code"].strip().upper()
            if code != product.code:
                if Product.query.filter_by(code=code).first():
                    return None, f"Product code '{code}' is already in use"
                product.code = code

        if "product_type" in data and data["product_type"].strip():
            product.product_type = data["product_type"].strip().lower()

        if "description" in data:
            product.description = data["description"].strip() or None

        if "notes" in data:
            product.notes = data["notes"].strip() or None

        if "sales_price" in data:
            try:
                sp = Decimal(str(data["sales_price"]))
                if sp < 0:
                    return None, "Sales price cannot be negative"
                product.sales_price = sp
            except Exception:
                return None, "Sales price must be a valid number"

        if "cost_price" in data:
            try:
                cp = Decimal(str(data["cost_price"]))
                if cp < 0:
                    return None, "Cost price cannot be negative"
                product.cost_price = cp
            except Exception:
                return None, "Cost price must be a valid number"

        if "tax_rate" in data:
            try:
                tr = Decimal(str(data["tax_rate"]))
                if tr < 0:
                    return None, "Tax rate cannot be negative"
                product.tax_rate = tr
            except Exception:
                return None, "Tax rate must be a valid number"

        if "is_active" in data:
            product.is_active = bool(data["is_active"])

        db.session.commit()
        return product.to_dict(include_variants=True), None

    @classmethod
    def toggle_product_active(cls, product_id: int) -> tuple[dict | None, str | None]:
        """Soft deactivates or reactivates a product."""
        product = db.session.get(Product, product_id)
        if not product:
            return None, "Product not found"
        product.is_active = not product.is_active
        db.session.commit()
        return product.to_dict(include_variants=True), None

    # --- Variant Operations ---

    @classmethod
    def add_variant(cls, product_id: int, data: dict) -> tuple[dict | None, str | None]:
        """Adds a variant to a product."""
        product = db.session.get(Product, product_id)
        if not product:
            return None, "Parent product not found"

        name = (data.get("variant_name") or "").strip()
        sku = (data.get("sku") or "").strip().upper()

        if not name or not sku:
            return None, "Variant name and unique SKU are required"

        try:
            add_price = Decimal(str(data.get("additional_price", 0)))
            if add_price < 0:
                return None, "Additional price cannot be negative"
        except Exception:
            return None, "Additional price must be a valid number"

        if ProductVariant.query.filter_by(sku=sku).first():
            return None, f"Variant SKU '{sku}' already exists"

        variant = ProductVariant(
            product_id=product.id,
            variant_name=name,
            sku=sku,
            additional_price=add_price,
            is_active=bool(data.get("is_active", True)),
        )
        db.session.add(variant)
        db.session.commit()

        return variant.to_dict(), None

    @classmethod
    def update_variant(cls, variant_id: int, data: dict) -> tuple[dict | None, str | None]:
        """Updates an existing variant."""
        variant = db.session.get(ProductVariant, variant_id)
        if not variant:
            return None, "Variant not found"

        if "variant_name" in data and data["variant_name"].strip():
            variant.variant_name = data["variant_name"].strip()

        if "sku" in data:
            sku = data["sku"].strip().upper()
            if sku != variant.sku:
                if ProductVariant.query.filter_by(sku=sku).first():
                    return None, f"Variant SKU '{sku}' already exists"
                variant.sku = sku

        if "additional_price" in data:
            try:
                ap = Decimal(str(data["additional_price"]))
                if ap < 0:
                    return None, "Additional price cannot be negative"
                variant.additional_price = ap
            except Exception:
                return None, "Additional price must be a valid number"

        if "is_active" in data:
            variant.is_active = bool(data["is_active"])

        db.session.commit()
        return variant.to_dict(), None

    @classmethod
    def calculate_effective_price(cls, product_id: int, variant_id: int | None = None) -> tuple[Decimal, Decimal, str | None]:
        """
        Calculates effective sales price and tax rate for a product and optional variant.
        Returns: (final_price, tax_rate, error)
        """
        product = db.session.get(Product, product_id)
        if not product:
            return Decimal("0.00"), Decimal("0.00"), "Product not found"
        if not product.is_active:
            return Decimal("0.00"), Decimal("0.00"), f"Product '{product.name}' is inactive and cannot be selected"

        price = product.sales_price
        if variant_id:
            variant = db.session.get(ProductVariant, variant_id)
            if not variant:
                return Decimal("0.00"), Decimal("0.00"), "Variant not found"
            if variant.product_id != product.id:
                return Decimal("0.00"), Decimal("0.00"), "Variant does not belong to specified product"
            if not variant.is_active:
                return Decimal("0.00"), Decimal("0.00"), f"Variant '{variant.variant_name}' is inactive and cannot be selected"
            price += variant.additional_price

        return price, product.tax_rate, None

