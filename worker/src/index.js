import { MongoClient } from "mongodb";

// The public site's origin(s). earthmothermango.com is the custom domain
// GitHub Pages now serves from; the old acb5764.github.io default is kept
// too since GitHub Pages still resolves it. Local dev servers (any
// http://localhost:*) are also allowed so `python3 -m http.server` works
// against this API without a separate mock.
const PROD_ORIGINS = [
  "https://earthmothermango.com",
  "https://www.earthmothermango.com",
  "https://acb5764.github.io",
];

// Only these fields ever leave this Worker. The `transactions` collection
// (the sale/cost ledger) is never queried here at all — this is belt-and-
// suspenders against a future field being added to `inventory` that
// shouldn't go public.
const PUBLIC_FIELDS = [
  "id", "name", "category", "variety", "propagation", "description", "unit",
  "price", "priceNote", "quantityOnHand", "lowStockThreshold", "status",
  "seasonNote", "photos", "featured", "sortOrder",
];

function toPublicItem(doc) {
  const out = {};
  for (const key of PUBLIC_FIELDS) {
    if (key in doc) out[key] = doc[key];
  }
  return out;
}

function isAllowedOrigin(origin) {
  if (!origin) return false;
  if (PROD_ORIGINS.includes(origin)) return true;
  try {
    return new URL(origin).hostname === "localhost";
  } catch {
    return false;
  }
}

function corsHeaders(origin) {
  const headers = {
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    Vary: "Origin",
  };
  if (isAllowedOrigin(origin)) headers["Access-Control-Allow-Origin"] = origin;
  return headers;
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const headers = corsHeaders(origin);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers });
    }
    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405, headers });
    }

    // A fresh connection per request, closed when done. Workers isolates
    // aren't a reliable place to keep a pooled TCP socket alive between
    // invocations (it goes stale and hangs the next request), and this
    // endpoint's traffic is far too low for that tradeoff to matter.
    // directConnection + a tiny pool keeps this to a single subrequest,
    // under the platform's per-invocation subrequest cap.
    let client;
    try {
      client = await MongoClient.connect(env.MONGODB_URI, {
        directConnection: true,
        maxPoolSize: 1,
        minPoolSize: 0,
        serverSelectionTimeoutMS: 5000,
      });
      const db = client.db(env.MONGODB_DB || "emm");
      const docs = await db.collection("inventory").find({}).toArray();

      docs.sort((a, b) => {
        const catCmp = (a.category || "").localeCompare(b.category || "");
        if (catCmp !== 0) return catCmp;
        return (a.sortOrder ?? 0) - (b.sortOrder ?? 0);
      });

      const payload = {
        updated: new Date().toISOString().slice(0, 10),
        items: docs.map(toPublicItem),
      };

      return new Response(JSON.stringify(payload), {
        headers: {
          ...headers,
          "Content-Type": "application/json",
          "Cache-Control": "public, max-age=30",
        },
      });
    } catch (err) {
      console.error(err);
      return new Response(JSON.stringify({ error: "inventory unavailable" }), {
        status: 502,
        headers: { ...headers, "Content-Type": "application/json" },
      });
    } finally {
      if (client) await client.close().catch(() => {});
    }
  },
};
