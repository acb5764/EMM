# emm-mongo MCP server

Private internal tooling — **not** part of the public static site. Gives the
agent tools to manage inventory + a transaction ledger in MongoDB.

The public site fetches live inventory through a separate Cloudflare Worker
(`worker/`) that queries the `inventory` collection directly — see
`worker/README.md`. Nothing from this MCP server or its Mongo connection is
exposed to the site or ever committed to the repo.

## Setup

1. `cp .env.example .env` and fill in `MONGODB_URI` (Atlas connection string,
   with network access restricted to your own IP, or a local `mongodb://localhost:27017`).
   `.env` is gitignored — never commit it.
2. Nothing else to install by hand: `.mcp.json` at the repo root runs this
   server with `uv run tools/mongo-tools/server.py`, and `uv` resolves the
   dependencies declared in the script header on first launch.
3. Restart Claude Code (or run `/mcp`) from the repo root so it picks up
   `.mcp.json`. Tools should then show up prefixed `emm-mongo__*`.

## Collections

- `inventory` — one document per catalog item, same shape as items in
  `data/inventory.json` (`id`, `name`, `category`, `variety`, `propagation`,
  `description`, `unit`, `price`, `priceNote`, `quantityOnHand`,
  `lowStockThreshold`, `status`, `seasonNote`, `photos`, `featured`,
  `sortOrder`).
- `transactions` — append-only ledger: `item_id`, `change_type` (`initial` /
  `restock` / `sale` / `adjustment` / `loss` / `transfer`), `quantity_delta`,
  `quantity_after`, `note`, `date`.
- `scion_sales` — append-only ledger for scion (cutting) sales: `quantity`,
  `variety` (free text, optional), `note`, `date`. Separate from
  `transactions` because scions are cut to order from a rotating assortment,
  not stocked as inventory items — there's no `item_id` to hang a normal
  transaction off of. Never queried by the public Worker.
- `variety_aliases` — small lookup table mapping an alternate name/nickname/
  abbreviation (`alias`, `alias_key` lowercased for matching) to the exact
  variety string stored on inventory items (`canonical`). Only needed for
  names that share no text with the real variety (e.g. "NDM" for "Nam Doc
  Mai") — parenthetical alt-names already on the item itself (e.g. "Diamond
  (HW-14)") are handled by substring matching and don't need an entry here.

## Tools

- `add_inventory_item` — insert a fresh-fruit / vegetables-herbs /
  cottage-foods item.
- `add_variety` — insert a trees-scions item. Per CLAUDE.md, the description
  should be enriched from the Tropical Acres Farms varietal PDF before
  calling this — the tool's own docstring repeats that instruction.
- `sell` — record a sale: decrements `quantityOnHand` and logs a `sale`
  transaction in one step. The everyday tool for a farm-stand sale.
- `restock` — record a restock: increments `quantityOnHand` and logs a
  `restock` transaction (pass `initial=True` for an item's first stock-in,
  logged as `initial` instead).
- `record_transaction` — general-purpose escape hatch for `adjustment`
  (recount corrections) or `loss` (spoilage/damage); same underlying
  atomic update+log as `sell`/`restock`.
- `transfer_pot_size` — "up-potting": move N trees of a variety from one pot
  size to another (e.g. "up-potted 2 Cotton Candy from 3-gallon to
  7-gallon"). `from_unit`/`to_unit` are optional — say just "up-potted 2
  Cotton Candy" and it infers `from_unit` when the variety only has stock at
  one pot size, and `to_unit` as the next standard size up (3 → 7 → 15 → 25
  gallon); it raises instead of guessing if stock exists at more than one
  size. Decrements the source listing, increments the destination listing
  (creating it automatically, following the existing
  `mango-tree-{slug}-{size}gal` / `"... (7-Gallon)"` naming convention, if
  it doesn't exist yet), and logs one linked `transfer` transaction on each
  side. Resolves variety through `variety_aliases` first, then matches by
  case-insensitive substring, and matches pot size by any text containing a
  number; raises instead of guessing if the variety match is ambiguous or
  the source doesn't have enough on hand.
- `add_variety_alias` / `list_variety_aliases` / `remove_variety_alias` —
  manage the `variety_aliases` lookup table, so a nickname or abbreviation
  (e.g. "NDM" for "Nam Doc Mai") gets recognized by `transfer_pot_size` and
  `get_sales_summary` even though it shares no text with the real variety
  name. `add_variety_alias` requires an exact (case-insensitive) match on an
  existing variety and raises with suggestions instead of guessing.
- `get_inventory` / `get_transactions` — read-side queries with basic filters.
- `get_sales_summary` — aggregates the transaction ledger for questions like
  "how many mallika did we sell last week" or "what's our best selling tree
  this month". Joins against `inventory` so it can filter by category/variety
  (transactions only store `item_id`), resolving variety through
  `variety_aliases` first, sums quantity per item over a date range, and
  returns them sorted highest first.
- `record_scion_sale` — log a scion sale (quantity, optional variety/note) to
  the `scion_sales` ledger.
- `get_scion_sales` — read-side query over `scion_sales`, returns matched
  records plus their summed `total_quantity`.
- `export_inventory_json` — writes the current `inventory` collection out to
  `data/inventory.json`, kept around for local reference/debugging only.
  **Not part of the publish path anymore** — see below.

## How a change reaches the public site

Nothing to commit or push. Use the tools to add items / record transactions
in Mongo as things actually happen (a sale, a restock, a new variety) and
the public site reflects it on the next page load, via `worker/` — a
Cloudflare Worker with its own read access to the `inventory` collection
(see `worker/README.md`).

The `transactions` collection (and Mongo's own history of it) never leaves
your database — the Worker only ever queries `inventory`, and only returns a
fixed set of public-safe fields from it.
