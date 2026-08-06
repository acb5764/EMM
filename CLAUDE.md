# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static inventory-catalog + "request to buy" website for Em_R_Mangoes (a small subtropical fruit farm/cottage-food business), meant to replace the bare `earthmothermango.com`. It's hosted on GitHub Pages, so the entire architecture is deliberately **no build step, no framework, no dependencies** — plain HTML/CSS/JS that GitHub Pages serves as-is.

## Running locally

There is no build/lint/test tooling — the only "command" is serving the directory, since `fetch()` of `data/inventory.json` fails under `file://`:

```bash
python3 -m http.server 8000
# then browse http://localhost:8000/
```

Click through nav links, category filters, cart add/remove, and form submissions after any change — there's no test suite to catch regressions.

## Architecture

**Shared chrome via Web Components, not a templating engine.** `js/partials.js` defines `<site-header>` and `<site-footer>` custom elements that every page includes as plain tags. There is no build step to generate this HTML, so header/nav changes (links, the theme toggle, the cart badge) only need to be made in `js/partials.js`, but any change to shared boilerplate elsewhere (the FOUC-prevention script, favicon, meta tags) must be hand-edited across every page — see "Duplicated per-page boilerplate" below.

**`data/inventory.json` is the single hand-edited source of truth for inventory.** The owner edits this file directly and pushes — there is no CMS or admin UI. `js/catalog.js` fetches it client-side and provides the shared rendering used by *both* `catalog.html` (full grid with filters/search) and `index.html` (featured-only grid): `itemCardHtml()`, `computeAvailability()` (derives In Stock/Low Stock/Sold Out/Seasonal/Coming Soon from `status` + `quantityOnHand`, rather than a hand-typed field), and `PLACEHOLDER_IMG` (an inline SVG data URI used as the `onerror` fallback for any product photo that doesn't exist yet under `images/products/`).

**Cart is `localStorage`-only, no backend.** `js/cart.js` stores `{itemId: quantity}` under key `emrCart`. `request.html`/`js/request.js` re-fetches `data/inventory.json` fresh on load and cross-checks cart contents against it, silently dropping/flagging anything that's gone Sold Out or been removed since it was added — the cart never trusts stale client state for price/availability.

**Forms submit to Formspree, not a server.** `js/request.js` and `js/contact.js` each POST to a Formspree endpoint via `fetch`, with a `mailto:` fallback shown on failure. Both currently hold placeholder endpoints (`REPLACE_WITH_YOUR_FORM_ID` / `REPLACE_WITH_YOUR_CONTACT_FORM_ID`) that need real Formspree form IDs before launch.

**Theming is dark-by-default with a manual light override**, driven by a `data-theme` attribute on `<html>` and CSS custom properties in `css/style.css` (`:root` = dark, `:root[data-theme="light"]` = overrides). Because there's no shared `<head>`, every page duplicates a small inline script that reads `localStorage['emrTheme']` and sets `data-theme` *before* the stylesheet loads, to avoid a flash of the wrong theme. If you add a new page, copy this snippet from an existing one.

**GitHub Pages subpath means relative paths only.** The site deploys at `<username>.github.io/Invnen`, not domain root, so every `href`/`src` must be relative with no leading slash (`catalog.html`, not `/catalog.html`) — an absolute path silently breaks in production while still working on `localhost`.

**No image pipeline.** Photos in `images/hero/` and `images/site/logo.jpg` were pulled from the live old site, had EXIF (including GPS) stripped, and were manually resized/compressed before committing (Pillow, no automated step). Follow the same manual process for any new images — there is no build-time optimization to lean on.

## Known TODOs in the code

Search for `TODO` — currently: two placeholder Formspree endpoints (`js/request.js`, `js/contact.js`) and an unconfirmed "Pay Now" link target in `contact.html`.
