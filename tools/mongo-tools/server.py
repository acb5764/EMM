# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp[cli]>=1.2.0,<2.0.0",
#     "pymongo[srv]>=4.6",
#     "python-dotenv>=1.0",
# ]
# ///
"""MCP server exposing tools to manage the Em_R_Mangoes inventory + transaction
ledger in MongoDB. Run via `uv run tools/mongo-tools/server.py` (see .mcp.json).

This is internal tooling for the site owner's private data (Mongo). It is
separate from the public static site, which continues to read only from
data/inventory.json — see export_inventory_json below for how the two connect.
"""

from typing import Optional

from mcp.server.fastmcp import FastMCP

from db import (
    REPO_ROOT,
    VALID_CATEGORIES,
    VALID_CHANGE_TYPES,
    VALID_PROPAGATION,
    VALID_STATUS,
    inventory_collection,
    now_iso,
    scion_sales_collection,
    strip_mongo_id,
    transactions_collection,
)

mcp = FastMCP("emm-mongo")


def _build_item_doc(
    *,
    id: str,
    name: str,
    category: str,
    description: str,
    unit: str,
    price: Optional[float],
    priceNote: Optional[str],
    quantityOnHand: int,
    lowStockThreshold: int,
    status: str,
    variety: Optional[str],
    propagation: str,
    seasonNote: Optional[str],
    photos: Optional[list],
    featured: bool,
    sortOrder: int,
) -> dict:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")
    if status not in VALID_STATUS:
        raise ValueError(f"status must be one of {sorted(VALID_STATUS)}")
    if propagation not in VALID_PROPAGATION:
        raise ValueError(f"propagation must be one of {sorted(VALID_PROPAGATION)}")
    if inventory_collection().find_one({"id": id}):
        raise ValueError(f"an inventory item with id '{id}' already exists")

    return {
        "id": id,
        "name": name,
        "category": category,
        "variety": variety,
        "propagation": propagation,
        "description": description,
        "unit": unit,
        "price": price,
        "priceNote": priceNote,
        "quantityOnHand": quantityOnHand,
        "lowStockThreshold": lowStockThreshold,
        "status": status,
        "seasonNote": seasonNote,
        "photos": photos or [],
        "featured": featured,
        "sortOrder": sortOrder,
    }


@mcp.tool()
def add_inventory_item(
    id: str,
    name: str,
    category: str,
    description: str,
    unit: str,
    price: Optional[float] = None,
    priceNote: Optional[str] = None,
    quantityOnHand: int = 0,
    lowStockThreshold: int = 1,
    status: str = "active",
    variety: Optional[str] = None,
    propagation: str = "unknown",
    seasonNote: Optional[str] = None,
    photos: Optional[list] = None,
    featured: bool = False,
    sortOrder: int = 100,
) -> dict:
    """Add a new item to the inventory collection (fresh-fruit, vegetables-herbs,
    or cottage-foods). For trees-scions varieties, use add_variety instead.

    Fields mirror data/inventory.json exactly so export_inventory_json can
    round-trip this straight to the public site. quantityOnHand defaults to 0
    (use record_transaction with change_type="initial" to stock it in, so the
    ledger has a record of where the starting count came from).
    """
    doc = _build_item_doc(
        id=id, name=name, category=category, description=description, unit=unit,
        price=price, priceNote=priceNote, quantityOnHand=quantityOnHand,
        lowStockThreshold=lowStockThreshold, status=status, variety=variety,
        propagation=propagation, seasonNote=seasonNote, photos=photos,
        featured=featured, sortOrder=sortOrder,
    )
    inventory_collection().insert_one(doc)
    return strip_mongo_id(doc)


@mcp.tool()
def update_price(
    item_id: Optional[str] = None,
    unit: Optional[str] = None,
    category: Optional[str] = None,
    price: Optional[float] = None,
    priceNote: Optional[str] = None,
    clear_price_note: bool = False,
) -> dict:
    """Update price and/or priceNote on one item (item_id) or in bulk across
    every item matching unit and/or category (e.g. unit="7-gallon pot" to
    reprice every 7-gallon pot at once).

    Must supply item_id, or at least one of unit/category. price/priceNote
    are only changed if you pass them — omit price to leave it untouched
    while only editing priceNote, or vice versa. Pass clear_price_note=True
    to null out priceNote (e.g. moving from "Call for pricing" to a flat
    price with no bulk-discount note); priceNote is otherwise left alone
    when omitted.
    """
    if price is None and priceNote is None and not clear_price_note:
        raise ValueError("nothing to update: pass price, priceNote, or clear_price_note")

    query: dict = {}
    if item_id:
        query["id"] = item_id
    if unit:
        query["unit"] = unit
    if category:
        query["category"] = category
    if not query:
        raise ValueError("must supply item_id, unit, and/or category to select items")

    update: dict = {}
    if price is not None:
        update["price"] = price
    if clear_price_note:
        update["priceNote"] = None
    elif priceNote is not None:
        update["priceNote"] = priceNote

    matched = list(inventory_collection().find(query, {"id": 1}))
    if not matched:
        raise ValueError(f"no inventory items matched {query}")

    inventory_collection().update_many(query, {"$set": update})
    return {"matched_count": len(matched), "item_ids": [m["id"] for m in matched], "set": update}


@mcp.tool()
def add_variety(
    id: str,
    name: str,
    variety: str,
    description: str,
    propagation: str = "unknown",
    unit: str = "3-gallon pot",
    price: Optional[float] = None,
    priceNote: Optional[str] = None,
    quantityOnHand: int = 0,
    lowStockThreshold: int = 1,
    status: str = "active",
    seasonNote: Optional[str] = None,
    photos: Optional[list] = None,
    featured: bool = False,
    sortOrder: int = 100,
) -> dict:
    """Add a new trees-scions variety to inventory.

    IMPORTANT — before calling this tool: per CLAUDE.md, fetch
    https://www.tropicalacresfarms.com/_files/ugd/9c9af8_4272686ce3364d649e876b6576ce8d1e.pdf
    and use it to write `description` with real varietal detail (flavor,
    origin/parentage, ripening season) rather than generic boilerplate. Do not
    call this tool with a placeholder description.

    quantityOnHand defaults to 0 — use record_transaction with
    change_type="initial" afterward to stock it in and keep the ledger
    consistent with every other item.
    """
    doc = _build_item_doc(
        id=id, name=name, category="trees-scions", description=description,
        unit=unit, price=price, priceNote=priceNote, quantityOnHand=quantityOnHand,
        lowStockThreshold=lowStockThreshold, status=status, variety=variety,
        propagation=propagation, seasonNote=seasonNote, photos=photos,
        featured=featured, sortOrder=sortOrder,
    )
    inventory_collection().insert_one(doc)
    return strip_mongo_id(doc)


def _apply_transaction(
    item_id: str, change_type: str, quantity_delta: int, note: Optional[str]
) -> dict:
    if change_type not in VALID_CHANGE_TYPES:
        raise ValueError(f"change_type must be one of {sorted(VALID_CHANGE_TYPES)}")

    item = inventory_collection().find_one({"id": item_id})
    if not item:
        raise ValueError(f"no inventory item with id '{item_id}'")

    quantity_after = item["quantityOnHand"] + quantity_delta
    if quantity_after < 0:
        raise ValueError(
            f"quantity_delta {quantity_delta} would take '{item_id}' below 0 "
            f"(currently {item['quantityOnHand']})"
        )

    inventory_collection().update_one(
        {"id": item_id}, {"$set": {"quantityOnHand": quantity_after}}
    )

    txn = {
        "item_id": item_id,
        "change_type": change_type,
        "quantity_delta": quantity_delta,
        "quantity_after": quantity_after,
        "note": note,
        "date": now_iso(),
    }
    result = transactions_collection().insert_one(txn)
    txn["_id"] = str(result.inserted_id)

    return {"transaction": txn, "item": strip_mongo_id({**item, "quantityOnHand": quantity_after})}


@mcp.tool()
def sell(item_id: str, quantity: int, note: Optional[str] = None) -> dict:
    """Record a sale: decrements quantityOnHand and logs a "sale" transaction
    in one step. quantity is the positive number of units sold."""
    if quantity <= 0:
        raise ValueError("quantity must be positive (units sold)")
    return _apply_transaction(item_id, "sale", -quantity, note)


@mcp.tool()
def restock(
    item_id: str, quantity: int, note: Optional[str] = None, initial: bool = False
) -> dict:
    """Record a restock: increments quantityOnHand and logs a "restock"
    transaction (or "initial" if this is the item's first stock-in) in one
    step. quantity is the positive number of units received."""
    if quantity <= 0:
        raise ValueError("quantity must be positive (units received)")
    return _apply_transaction(item_id, "initial" if initial else "restock", quantity, note)


@mcp.tool()
def record_transaction(
    item_id: str,
    change_type: str,
    quantity_delta: int,
    note: Optional[str] = None,
) -> dict:
    """Log a stock change and apply it to inventory.quantityOnHand in one step.
    General-purpose escape hatch — prefer sell/restock for those cases. Use
    this directly for "adjustment" (recount corrections, either direction) or
    "loss" (spoilage/damage, always negative).

    This is the only supported way to change quantityOnHand — it keeps the
    transactions ledger and the inventory snapshot from drifting apart.

    change_type: one of "initial", "restock", "sale", "adjustment", "loss".
    quantity_delta: signed integer. The resulting quantityOnHand must not go
    below 0.
    """
    return _apply_transaction(item_id, change_type, quantity_delta, note)


@mcp.tool()
def record_scion_sale(
    quantity: int, variety: Optional[str] = None, note: Optional[str] = None
) -> dict:
    """Log a scion (cutting) sale to a dedicated scion_sales ledger.

    Scions are cut to order from a rotating assortment of source trees, not
    stocked, so they don't belong in the inventory/transactions system (which
    requires an existing inventory item and tracks quantityOnHand). This is a
    separate append-only collection just for scion sale records — it never
    touches inventory and is never queried by the public Worker.

    quantity is the positive number of scions sold. variety is optional
    free text (e.g. "Nam Doc Mai") since specific varieties aren't tracked
    as items yet.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive (units sold)")
    doc = {
        "quantity": quantity,
        "variety": variety,
        "note": note,
        "date": now_iso(),
    }
    result = scion_sales_collection().insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@mcp.tool()
def get_scion_sales(
    since: Optional[str] = None, until: Optional[str] = None, limit: int = 100
) -> dict:
    """Query the scion_sales ledger. since/until are ISO-8601 date or
    datetime strings, compared lexicographically against the stored date.

    Returns {"total_quantity": <sum over matched records>, "sales": [...]}.
    """
    query: dict = {}
    if since or until:
        date_filter = {}
        if since:
            date_filter["$gte"] = since
        if until:
            date_filter["$lte"] = until
        query["date"] = date_filter

    cursor = scion_sales_collection().find(query).sort("date", -1).limit(limit)
    sales = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        sales.append(doc)
    return {"total_quantity": sum(s["quantity"] for s in sales), "sales": sales}


@mcp.tool()
def get_inventory(
    category: Optional[str] = None,
    status: Optional[str] = None,
    low_stock_only: bool = False,
    search: Optional[str] = None,
) -> list[dict]:
    """Query current inventory. All filters are optional and AND together.

    low_stock_only returns items where quantityOnHand <= lowStockThreshold.
    search does a case-insensitive substring match against name/variety.
    """
    query: dict = {}
    if category:
        query["category"] = category
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"variety": {"$regex": search, "$options": "i"}},
        ]

    items = [strip_mongo_id(d) for d in inventory_collection().find(query)]
    if low_stock_only:
        items = [i for i in items if i["quantityOnHand"] <= i.get("lowStockThreshold", 1)]
    items.sort(key=lambda i: (i.get("category", ""), i.get("sortOrder", 0)))
    return items


@mcp.tool()
def get_transactions(
    item_id: Optional[str] = None,
    change_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Query the transaction ledger. since/until are ISO-8601 date or
    datetime strings, compared lexicographically against the stored date."""
    query: dict = {}
    if item_id:
        query["item_id"] = item_id
    if change_type:
        query["change_type"] = change_type
    if since or until:
        date_filter = {}
        if since:
            date_filter["$gte"] = since
        if until:
            date_filter["$lte"] = until
        query["date"] = date_filter

    cursor = transactions_collection().find(query).sort("date", -1).limit(limit)
    out = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        out.append(doc)
    return out


@mcp.tool()
def get_sales_summary(
    since: Optional[str] = None,
    until: Optional[str] = None,
    change_type: str = "sale",
    category: Optional[str] = None,
    variety: Optional[str] = None,
    item_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    """Aggregate the transaction ledger for reporting questions like "how many
    mallika did we sell last week" or "what's our best selling tree this
    month" — take entry 0 of by_item, sorted highest quantity first.

    Joins transactions against inventory so results can be filtered/grouped
    by category or variety (transactions only store item_id).

    since/until: ISO-8601 date or datetime strings (inclusive), compared
    lexicographically against the stored transaction date, e.g. "2026-08-01"
    for start-of-month or "2026-08-03" for a week-ago cutoff.
    change_type: one of "initial", "restock", "sale", "adjustment", "loss"
    (default "sale"). Quantities are summed by magnitude, so stick to a
    single change_type per call rather than mixing signs.
    category/variety: optional filters against the joined inventory item
    (variety is a case-insensitive substring match, e.g. "mallika").
    item_id: optional exact item id filter, bypassing the category/variety
    join.
    limit: if set, only return the top N items by quantity.

    Returns {"since", "until", "change_type", "total_quantity",
    "by_item": [{"item_id", "name", "variety", "category", "quantity"}, ...]}
    sorted by quantity descending.
    """
    txn_query: dict = {"change_type": change_type}
    if item_id:
        txn_query["item_id"] = item_id
    if since or until:
        date_filter = {}
        if since:
            date_filter["$gte"] = since
        if until:
            date_filter["$lte"] = until
        txn_query["date"] = date_filter

    items_by_id = {d["id"]: strip_mongo_id(d) for d in inventory_collection().find()}

    if not item_id and (category or variety):
        allowed_ids = {
            i["id"] for i in items_by_id.values()
            if (not category or i.get("category") == category)
            and (not variety or variety.lower() in (i.get("variety") or "").lower())
        }
        if not allowed_ids:
            return {
                "since": since, "until": until, "change_type": change_type,
                "total_quantity": 0, "by_item": [],
            }
        txn_query["item_id"] = {"$in": sorted(allowed_ids)}

    totals: dict = {}
    for txn in transactions_collection().find(txn_query):
        totals[txn["item_id"]] = totals.get(txn["item_id"], 0) + abs(txn["quantity_delta"])

    by_item = []
    for iid, qty in totals.items():
        item = items_by_id.get(iid, {})
        by_item.append({
            "item_id": iid,
            "name": item.get("name", iid),
            "variety": item.get("variety"),
            "category": item.get("category"),
            "quantity": qty,
        })
    by_item.sort(key=lambda x: x["quantity"], reverse=True)
    if limit:
        by_item = by_item[:limit]

    return {
        "since": since,
        "until": until,
        "change_type": change_type,
        "total_quantity": sum(totals.values()),
        "by_item": by_item,
    }


@mcp.tool()
def export_inventory_json(path: str = "data/inventory.json") -> dict:
    """Export the current inventory collection to the public site's JSON file.

    Writes {updated, items} to `path` (relative to the repo root) in the same
    shape catalog.js expects. This does NOT commit or push — review the diff
    and commit it yourself so the public repo's history stays deliberate.
    """
    import json
    from datetime import date

    items = [strip_mongo_id(d) for d in inventory_collection().find()]
    items.sort(key=lambda i: (i.get("category", ""), i.get("sortOrder", 0)))

    out_path = (REPO_ROOT / path).resolve()
    if REPO_ROOT not in out_path.parents and out_path != REPO_ROOT:
        raise ValueError("path must stay within the repo")

    payload = {"updated": date.today().isoformat(), "items": items}
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    return {"path": str(out_path.relative_to(REPO_ROOT)), "item_count": len(items)}


if __name__ == "__main__":
    mcp.run()
