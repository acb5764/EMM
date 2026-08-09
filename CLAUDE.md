# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static inventory-catalog + "request to buy" website for Em_R_Mangoes (a small subtropical fruit farm/cottage-food business), meant to replace the bare `earthmothermango.com`. It's hosted on GitHub Pages, so the site itself is deliberately **no build step, no framework, no dependencies** — plain HTML/CSS/JS that GitHub Pages serves as-is. The one exception is `worker/`, a small Cloudflare Worker (own `package.json`, deployed separately via `wrangler`) that proxies live inventory out of MongoDB — see "MongoDB is the source of truth" below. It's not part of what GitHub Pages serves and doesn't affect the "no build step" property of the site itself.

## Running locally

There is no build/lint/test tooling for the site itself — the only "command" is serving the directory, since `fetch()` of the inventory API fails under `file://`:

```bash
python3 -m http.server 8000
# then browse http://localhost:8000/
```

Click through nav links, category filters, cart add/remove, and form submissions after any change — there's no test suite to catch regressions.

## Architecture

**Shared chrome via Web Components, not a templating engine.** `js/partials.js` defines `<site-header>` and `<site-footer>` custom elements that every page includes as plain tags. There is no build step to generate this HTML, so header/nav changes (links, the theme toggle, the cart badge) only need to be made in `js/partials.js`, but any change to shared boilerplate elsewhere (the FOUC-prevention script, favicon, meta tags) must be hand-edited across every page — see "Duplicated per-page boilerplate" below.

**MongoDB is the source of truth for inventory; the site never reads a committed snapshot.** The owner (via Claude + the `emm-mongo` MCP server, see `tools/mongo-tools/`) manages a Mongo Atlas `inventory` collection plus an append-only `transactions` ledger (sales, restocks, adjustments, losses). A small Cloudflare Worker (`worker/`) is the only thing with DB credentials: it queries `inventory` server-side, strips it down to public catalog fields (defense in depth — `transactions` is never queried by the Worker at all, so ledger/cost data structurally cannot reach the public site), and serves `{updated, items}` as JSON over HTTPS with CORS locked to the production origin (plus `localhost` for dev). `js/catalog.js`, `js/request.js`, and `js/inventory.js` each fetch that URL via an `INVENTORY_API_URL` constant at the top of the file (currently a `REPLACE_WITH_WORKER_URL` placeholder — see `worker/README.md` for the one-time `wrangler deploy` setup). This means inventory updates go live the moment they're written to Mongo — no export, no commit, no push, and no inventory data of any kind lives in the git repo or its history. `js/catalog.js` provides the shared rendering used by _both_ `catalog.html` (full grid with filters/search) and `index.html` (featured-only grid): `itemCardHtml()`, `computeAvailability()` (derives In Stock/Low Stock/Sold Out/Seasonal/Coming Soon from `status` + `quantityOnHand`, rather than a hand-typed field), and `PLACEHOLDER_IMG` (an inline SVG data URI used as the `onerror` fallback for any product photo that doesn't exist yet under `images/products/`). Every `trees-scions` item also carries a `propagation` field (`"grafted"`, `"seed"`, or `"unknown"`) — descriptions no longer assert "Grafted" or "grown on-site" as prose, since propagation method is unconfirmed for most varieties and sourcing (on-site vs. wholesaler) isn't tracked at all. `catalog.js`/`catalog.html`/`index.html` only render a Grafted/From Seed tag when known; the staff-only `inventory.html` table shows the raw value (including "Unknown") so it doubles as a checklist for filling propagation in over time.

`data/inventory.json` still exists in the repo as a historical snapshot but is **no longer fetched by any page** — don't edit it expecting it to reach the site; use the `emm-mongo` MCP tools instead.

**Cart is `localStorage`-only, no backend.** `js/cart.js` stores `{itemId: quantity}` under key `emrCart`. `request.html`/`js/request.js` re-fetches `data/inventory.json` fresh on load and cross-checks cart contents against it, silently dropping/flagging anything that's gone Sold Out or been removed since it was added — the cart never trusts stale client state for price/availability.

**Forms submit to Formspree, not a server.** `js/request.js` and `js/contact.js` each POST to a Formspree endpoint via `fetch`, with a `mailto:` fallback shown on failure. Both currently hold placeholder endpoints (`REPLACE_WITH_YOUR_FORM_ID` / `REPLACE_WITH_YOUR_CONTACT_FORM_ID`) that need real Formspree form IDs before launch.

**Theming is dark-by-default with a manual light override**, driven by a `data-theme` attribute on `<html>` and CSS custom properties in `css/style.css` (`:root` = dark, `:root[data-theme="light"]` = overrides). Because there's no shared `<head>`, every page duplicates a small inline script that reads `localStorage['emrTheme']` and sets `data-theme` _before_ the stylesheet loads, to avoid a flash of the wrong theme. If you add a new page, copy this snippet from an existing one.

**GitHub Pages subpath means relative paths only.** The site deploys at `<username>.github.io/Invnen`, not domain root, so every `href`/`src` must be relative with no leading slash (`catalog.html`, not `/catalog.html`) — an absolute path silently breaks in production while still working on `localhost`.

**No image pipeline.** Photos in `images/hero/` and `images/site/logo.jpg` were pulled from the live old site, had EXIF (including GPS) stripped, and were manually resized/compressed before committing (Pillow, no automated step). Follow the same manual process for any new images — there is no build-time optimization to lean on.

## Known TODOs in the code

Search for `TODO` — currently: two placeholder Formspree endpoints (`js/request.js`, `js/contact.js`), an unconfirmed "Pay Now" link target in `contact.html`, and a placeholder `INVENTORY_API_URL` (`REPLACE_WITH_WORKER_URL`) in `js/catalog.js`, `js/request.js`, and `js/inventory.js` that needs the real deployed Worker URL — see `worker/README.md`.

## Rules

Any addition of new varieties should use https://www.tropicalacresfarms.com/_files/ugd/9c9af8_4272686ce3364d649e876b6576ce8d1e.pdf to enrich the description before adding to the inventory
