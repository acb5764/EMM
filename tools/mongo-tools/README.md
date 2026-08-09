# emm-mongo MCP server

Private internal tooling — **not** part of the public static site. Gives the
agent tools to manage inventory + a transaction ledger in MongoDB, decoupled
from `data/inventory.json` (which stays the public, hand-edited snapshot the
site actually fetches).

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
  `restock` / `sale` / `adjustment` / `loss`), `quantity_delta`,
  `quantity_after`, `note`, `date`.

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
- `get_inventory` / `get_transactions` — read-side queries with basic filters.
- `export_inventory_json` — writes the current `inventory` collection out to
  `data/inventory.json` in the exact shape the public site expects. Doesn't
  commit or push — review the diff and commit it yourself.

## Publishing a change to the public site

1. Use the tools to add items / record transactions in Mongo as things
   actually happen.
2. When ready to publish, call `export_inventory_json`.
3. Review the resulting diff in `data/inventory.json`, commit, push.

The `transactions` collection (and Mongo's own history of it) never leaves
your database — only current-state snapshots ever reach the public repo.
