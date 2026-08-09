# emm-inventory-api (Cloudflare Worker)

Public, read-only proxy in front of the `inventory` collection in MongoDB
Atlas. This is what the static site actually fetches at runtime — nothing
about live inventory is ever committed to the repo anymore.

`src/index.js` opens a MongoDB connection (native driver, over Workers' TCP
socket support — `nodejs_compat` + a compatibility date after 2024-09-23 is
required for this to work) and returns only the public catalog fields listed
in `PUBLIC_FIELDS`. The `transactions` ledger collection is never queried
here at all.

## One-time setup

1. `cd worker && npm install`
2. `npx wrangler login` (opens a browser to authorize the CLI against your
   Cloudflare account)
3. `npx wrangler secret put MONGODB_URI` and paste the same Atlas connection
   string used in `tools/mongo-tools/.env` (ideally a **separate, read-only**
   Atlas database user scoped to the `inventory` collection only, so this
   Worker can never write or touch `transactions` even if compromised).
4. `npx wrangler deploy` — prints the live URL, something like
   `https://emm-inventory-api.<your-subdomain>.workers.dev`.
5. Put that URL into the `INVENTORY_API_URL` constant at the top of
   `js/catalog.js`, `js/request.js`, and `js/inventory.js` (currently a
   `REPLACE_WITH_WORKER_URL` placeholder, same pattern as the Formspree
   TODOs).

## Local dev

`npx wrangler dev` runs the Worker locally (still talking to real Atlas —
there's no local Mongo mock here). CORS in `src/index.js` allows any
`http://localhost:*` origin plus the production GitHub Pages origin, so the
site's own `python3 -m http.server 8000` workflow keeps working against
either the deployed Worker or `wrangler dev`.

## Redeploying after code changes

`npx wrangler deploy` again — same URL, no need to touch the site's fetch
calls after the first setup.
