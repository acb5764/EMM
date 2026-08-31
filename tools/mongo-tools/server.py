# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp[cli]>=1.2.0,<2.0.0",
#     "pymongo[srv]>=4.6",
#     "python-dotenv>=1.0",
# ]
# ///
"""MCP server exposing tools to manage the Earth Mother Mango inventory + transaction
ledger in MongoDB. Run via `uv run tools/mongo-tools/server.py` (see .mcp.json).

This is internal tooling for the site owner's private data (Mongo). It is
separate from the public static site, which continues to read only from
data/inventory.json — see export_inventory_json below for how the two connect.
"""

import re
import uuid
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
    variety_aliases_collection,
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
        raise ValueError(
            f"propagation must be one of {sorted(VALID_PROPAGATION)}")
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
        raise ValueError(
            "nothing to update: pass price, priceNote, or clear_price_note")

    query: dict = {}
    if item_id:
        query["id"] = item_id
    if unit:
        query["unit"] = unit
    if category:
        query["category"] = category
    if not query:
        raise ValueError(
            "must supply item_id, unit, and/or category to select items")

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
        raise ValueError(
            f"change_type must be one of {sorted(VALID_CHANGE_TYPES)}")

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
    General-purpose escape hatch — prefer sell/restock/transfer_pot_size for
    those cases. Use this directly for "adjustment" (recount corrections,
    either direction) or "loss" (spoilage/damage, always negative).

    This is the only supported way to change quantityOnHand — it keeps the
    transactions ledger and the inventory snapshot from drifting apart.

    change_type: one of "initial", "restock", "sale", "adjustment", "loss",
    "transfer". quantity_delta: signed integer. The resulting
    quantityOnHand must not go below 0.
    """
    return _apply_transaction(item_id, change_type, quantity_delta, note)


_POT_SIZE_RE = re.compile(r"(\d+)")
_POT_SUFFIX_ID_RE = re.compile(r"-\d+gal$")
_POT_SUFFIX_NAME_RE = re.compile(r"\s*\(\d+-Gallon\)$", re.IGNORECASE)

# Standard per-tier pricing observed across the catalog today — used only as
# a starting point when up-potting has to create a brand-new destination
# listing. update_price can correct it afterward if a variety is priced
# differently.
_TIER_PRICE_DEFAULTS = {
    "7-gallon pot": 80.0,
    "15-gallon pot": 160.0,
    "25-gallon pot": 260.0,
}


def _normalize_pot_unit(raw: str) -> str:
    match = _POT_SIZE_RE.search(raw)
    if not match:
        raise ValueError(
            f"couldn't find a pot size in '{raw}' — try e.g. '3-gallon' or '7-gallon pot'"
        )
    return f"{match.group(1)}-gallon pot"


def _resolve_variety(variety: str) -> str:
    """Translate a registered alias/nickname/abbreviation (see
    add_variety_alias) to its canonical variety string. Looks up an exact
    case-insensitive match on the alias; returns the input unchanged if
    nothing is registered for it, so callers can always feed the result
    straight into substring matching."""
    alias_key = variety.strip().casefold()
    doc = variety_aliases_collection().find_one({"alias_key": alias_key})
    return doc["canonical"] if doc else variety


def _exact_variety_match(variety: str) -> Optional[str]:
    """Case-insensitive *exact* match against existing variety strings
    (unlike _find_variety_items's substring match) — used when registering
    an alias, where we need one unambiguous canonical target."""
    needle = variety.strip().casefold()
    for doc in inventory_collection().find({"category": "trees-scions"}, {"variety": 1}):
        v = doc.get("variety")
        if v and v.casefold() == needle:
            return v
    return None


def _find_variety_items(variety: str) -> list[dict]:
    variety = _resolve_variety(variety)
    needle = variety.strip().casefold()
    if not needle:
        raise ValueError("variety must not be blank")
    matches = []
    for doc in inventory_collection().find({"category": "trees-scions"}):
        hay = (doc.get("variety") or "").casefold()
        if hay and (needle in hay or hay in needle):
            matches.append(doc)
    return matches


@mcp.tool()
def transfer_pot_size(
    variety: str,
    from_unit: str,
    to_unit: str,
    quantity: int,
    note: Optional[str] = None,
    new_item_price: Optional[float] = None,
) -> dict:
    """Move trees from one pot size to another for the same variety —
    "up-potting" — e.g. someone says "we up-potted 2 Cotton Candy" or "we
    put 3 Carrie trees in 7-gallon pots". Decrements the source listing and
    increments (or creates) the destination listing for the same variety,
    logging one linked "transfer" transaction on each side, so the ledger
    shows where the trees went instead of looking like an unexplained loss
    plus an unexplained restock.

    variety is first checked against registered aliases (see
    add_variety_alias) — e.g. if "NDM" has been registered as an alias for
    "Nam Doc Mai", saying "up-pot 2 NDM" resolves correctly — then matched
    case-insensitively as a substring against existing trees-scions items
    (either direction), so "cotton candy" matches "Cotton Candy". This also
    handles varieties whose stored name already carries a parenthetical
    alt-name (e.g. variety "Diamond (HW-14)" matches either "Diamond" or
    "HW-14" without needing a registered alias). from_unit/to_unit accept
    loose pot-size text — "3-gallon", "3 gal", and "3-gallon pot" all resolve
    the same way — as long as they contain a number.

    Fault tolerance: raises a clear error (rather than guessing) if variety
    matches zero or more than one item at from_unit, or if from_unit doesn't
    have enough quantityOnHand to cover quantity — a typo or an ambiguous
    variety name never silently moves the wrong trees. If the destination pot
    size doesn't have a listing yet for this variety, one is created
    automatically, cloning name/description/propagation/status from the
    source and following the existing "(7-Gallon)"-style id/name suffix
    convention. Pass new_item_price to set its price explicitly; otherwise it
    falls back to this catalog's standard price for that pot size where
    known (7/15/25-gallon), or None ("Call for pricing") otherwise.
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive (units moved)")

    from_norm = _normalize_pot_unit(from_unit)
    to_norm = _normalize_pot_unit(to_unit)
    if from_norm == to_norm:
        raise ValueError(
            f"from_unit and to_unit are both '{from_norm}' — nothing to transfer")

    candidates = _find_variety_items(variety)
    source_matches = [d for d in candidates if d["unit"] == from_norm]
    if not source_matches:
        available = sorted(
            {f"{d.get('variety')} ({d['unit']})" for d in candidates})
        if available:
            raise ValueError(
                f"no '{from_norm}' listing matches variety '{variety}'. "
                f"Found this variety at: {', '.join(available)}"
            )
        raise ValueError(
            f"no trees-scions item matches variety '{variety}'")
    if len(source_matches) > 1:
        ids = ", ".join(
            f"{d['id']} ({d.get('variety')})" for d in source_matches)
        raise ValueError(
            f"variety '{variety}' at {from_norm} is ambiguous — matches: {ids}. "
            "Use a more specific variety name."
        )
    source = source_matches[0]

    if source["quantityOnHand"] < quantity:
        raise ValueError(
            f"only {source['quantityOnHand']} of '{source['name']}' on hand at "
            f"{from_norm}, can't move {quantity}"
        )

    exact_variety = source.get("variety")
    dest_matches = [
        d for d in candidates
        if d["unit"] == to_norm and d.get("variety") == exact_variety
    ]
    if len(dest_matches) > 1:
        ids = ", ".join(d["id"] for d in dest_matches)
        raise ValueError(
            f"variety '{exact_variety}' at {to_norm} is ambiguous — matches: {ids}. "
            "Resolve the duplicate listing before transferring."
        )

    transfer_id = uuid.uuid4().hex[:8]
    move_note = note or f"up-potted from {from_norm} to {to_norm}"
    linked_note = f"{move_note} (transfer {transfer_id})"

    dest = dest_matches[0] if dest_matches else None
    created_dest = False
    if dest is None:
        size_num = to_norm.split("-")[0]
        base_id = _POT_SUFFIX_ID_RE.sub("", source["id"])
        new_id = f"{base_id}-{size_num}gal"
        base_name = _POT_SUFFIX_NAME_RE.sub("", source["name"])
        new_name = f"{base_name} ({size_num}-Gallon)"
        price = new_item_price if new_item_price is not None else _TIER_PRICE_DEFAULTS.get(
            to_norm)

        dest_doc = _build_item_doc(
            id=new_id,
            name=new_name,
            category="trees-scions",
            description=source.get("description", ""),
            unit=to_norm,
            price=price,
            priceNote=None if price is not None else source.get(
                "priceNote"),
            quantityOnHand=0,
            lowStockThreshold=source.get("lowStockThreshold", 1),
            status=source.get("status", "active"),
            variety=exact_variety,
            propagation=source.get("propagation", "unknown"),
            seasonNote=source.get("seasonNote"),
            photos=None,
            featured=False,
            sortOrder=source.get("sortOrder", 100) + 1,
        )
        inventory_collection().insert_one(dest_doc)
        dest = dest_doc
        created_dest = True

    from_result = _apply_transaction(
        source["id"], "transfer", -quantity, linked_note)
    to_result = _apply_transaction(dest["id"], "transfer", quantity, linked_note)

    return {
        "transfer_id": transfer_id,
        "from": from_result,
        "to": to_result,
        "destination_created": created_dest,
    }


@mcp.tool()
def add_variety_alias(alias: str, canonical_variety: str) -> dict:
    """Register alias as an alternate name for canonical_variety, so tools
    that take a variety (transfer_pot_size, get_sales_summary) recognize it
    even when it shares no text with the real name — e.g.
    add_variety_alias("NDM", "Nam Doc Mai") lets "up-pot 2 NDM" resolve
    correctly. (Parenthetical alt-names already stored on the item itself,
    like "Diamond (HW-14)", don't need this — those already match either
    half via substring. This is for names that aren't substrings at all:
    abbreviations, nicknames, alternate spellings.)

    canonical_variety must be an *exact* case-insensitive match to an
    existing trees-scions item's variety field — if it's ambiguous or not
    found, this raises with the closest candidates rather than guessing.

    Re-registering the same alias (case-insensitive) overwrites the previous
    mapping, so fixing a mistake doesn't require a separate remove step.
    """
    alias_key = alias.strip().casefold()
    if not alias_key:
        raise ValueError("alias must not be blank")
    canonical = canonical_variety.strip()
    if not canonical:
        raise ValueError("canonical_variety must not be blank")

    canonical_exact = _exact_variety_match(canonical)
    if canonical_exact is None:
        candidates = _find_variety_items(canonical)
        if candidates:
            options = sorted(
                {d.get("variety") for d in candidates if d.get("variety")})
            raise ValueError(
                f"'{canonical}' isn't an exact variety match. Did you mean: "
                f"{', '.join(options)}?"
            )
        raise ValueError(f"no trees-scions variety matches '{canonical}'")

    existing = variety_aliases_collection().find_one({"alias_key": alias_key})
    variety_aliases_collection().update_one(
        {"alias_key": alias_key},
        {"$set": {"alias_key": alias_key, "alias": alias.strip(),
                   "canonical": canonical_exact}},
        upsert=True,
    )
    return {
        "alias": alias.strip(),
        "canonical": canonical_exact,
        "replaced": existing["canonical"] if existing else None,
    }


@mcp.tool()
def list_variety_aliases(canonical_variety: Optional[str] = None) -> list[dict]:
    """List registered variety aliases. Optionally filter to aliases pointing
    at one canonical_variety (case-insensitive exact match)."""
    docs = [strip_mongo_id(d) for d in variety_aliases_collection().find()]
    for d in docs:
        d.pop("alias_key", None)
    if canonical_variety:
        needle = canonical_variety.strip().casefold()
        docs = [d for d in docs if d["canonical"].casefold() == needle]
    docs.sort(key=lambda d: d["alias"].casefold())
    return docs


@mcp.tool()
def remove_variety_alias(alias: str) -> dict:
    """Delete a registered variety alias (case-insensitive match on alias)."""
    alias_key = alias.strip().casefold()
    removed = variety_aliases_collection().find_one_and_delete(
        {"alias_key": alias_key})
    if not removed:
        raise ValueError(f"no alias '{alias}' is registered")
    return {"removed": strip_mongo_id(removed)}


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
        items = [i for i in items if i["quantityOnHand"]
                 <= i.get("lowStockThreshold", 1)]
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
    change_type: one of "initial", "restock", "sale", "adjustment", "loss",
    "transfer" (default "sale"). Quantities are summed by magnitude, so stick to a
    single change_type per call rather than mixing signs.
    category/variety: optional filters against the joined inventory item
    (variety is resolved through registered aliases — see
    add_variety_alias — then matched as a case-insensitive substring,
    e.g. "mallika" or a registered abbreviation like "NDM").
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

    items_by_id = {d["id"]: strip_mongo_id(
        d) for d in inventory_collection().find()}

    if not item_id and (category or variety):
        resolved_variety = _resolve_variety(variety) if variety else None
        allowed_ids = {
            i["id"] for i in items_by_id.values()
            if (not category or i.get("category") == category)
            and (not resolved_variety or resolved_variety.lower() in (i.get("variety") or "").lower())
        }
        if not allowed_ids:
            return {
                "since": since, "until": until, "change_type": change_type,
                "total_quantity": 0, "by_item": [],
            }
        txn_query["item_id"] = {"$in": sorted(allowed_ids)}

    totals: dict = {}
    for txn in transactions_collection().find(txn_query):
        totals[txn["item_id"]] = totals.get(
            txn["item_id"], 0) + abs(txn["quantity_delta"])

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
