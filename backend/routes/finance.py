"""Finance reporting API endpoints (Module 7 contracts)."""

from flask import Blueprint, current_app, jsonify, request

from services import finance_service as svc

bp = Blueprint("finance", __name__, url_prefix="/api/finance")


def _range():
    from_date = svc.parse_date(request.args.get("from"), "from")
    to_date = svc.parse_date(request.args.get("to"), "to")
    svc.validate_range(from_date, to_date)
    return from_date, to_date


def _pagination():
    default_per_page = current_app.config["DEFAULT_PER_PAGE"]
    max_per_page = current_app.config["MAX_PER_PAGE"]

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", default_per_page, type=int)

    if page is None or page < 1:
        raise svc.ApiError("Invalid 'page': must be a positive integer.")
    if per_page is None or per_page < 1 or per_page > max_per_page:
        raise svc.ApiError(f"Invalid 'per_page': must be between 1 and {max_per_page}.")

    return page, per_page


@bp.get("/summary")
def summary():
    from_date, to_date = _range()
    ttl = current_app.config["CACHE_TTL_SECONDS"]
    cache_key = f"summary:{from_date}:{to_date}"
    payload = svc.cached(
        cache_key, ttl, lambda: svc.summary(from_date=from_date, to_date=to_date)
    )
    return jsonify(payload)


@bp.get("/revenue")
def revenue():
    from_date, to_date = _range()
    granularity = (request.args.get("granularity") or "month").lower()
    ttl = current_app.config["CACHE_TTL_SECONDS"]
    cache_key = f"revenue:{granularity}:{from_date}:{to_date}"
    payload = svc.cached(
        cache_key,
        ttl,
        lambda: svc.revenue_series(
            from_date=from_date, to_date=to_date, granularity=granularity
        ),
    )
    return jsonify(payload)


@bp.get("/invoices")
def invoices():
    page, per_page = _pagination()
    from_date, to_date = _range()

    payload = svc.list_invoices(
        page=page,
        per_page=per_page,
        status=request.args.get("status"),
        customer=request.args.get("customer"),
        customer_id=request.args.get("customer_id", type=int),
        date_field=request.args.get("date_field", "invoice_date"),
        from_date=from_date,
        to_date=to_date,
        amount_min=svc.parse_amount(request.args.get("amount_min"), "amount_min"),
        amount_max=svc.parse_amount(request.args.get("amount_max"), "amount_max"),
        q=request.args.get("q"),
        sort=request.args.get("sort", "invoice_date"),
        order=request.args.get("order", "desc"),
    )
    return jsonify(payload)


@bp.get("/payments")
def payments():
    page, per_page = _pagination()
    from_date, to_date = _range()

    payload = svc.list_payments(
        page=page,
        per_page=per_page,
        status=request.args.get("status", "successful"),
        method=request.args.get("method"),
        customer=request.args.get("customer"),
        customer_id=request.args.get("customer_id", type=int),
        invoice_number=request.args.get("invoice"),
        from_date=from_date,
        to_date=to_date,
        amount_min=svc.parse_amount(request.args.get("amount_min"), "amount_min"),
        amount_max=svc.parse_amount(request.args.get("amount_max"), "amount_max"),
        q=request.args.get("q"),
        order=request.args.get("order", "desc"),
    )
    return jsonify(payload)


@bp.get("/subscriptions")
def subscriptions():
    page, per_page = _pagination()
    payload = svc.list_subscriptions(
        page=page,
        per_page=per_page,
        status=request.args.get("status"),
        product=request.args.get("product"),
        customer_id=request.args.get("customer_id", type=int),
        q=request.args.get("q"),
        order=request.args.get("order", "desc"),
    )
    return jsonify(payload)


@bp.get("/subscriptions/summary")
def subscriptions_summary():
    ttl = current_app.config["CACHE_TTL_SECONDS"]
    payload = svc.cached(
        "subscriptions:summary",
        ttl,
        svc.subscription_summary,
    )
    return jsonify(payload)

