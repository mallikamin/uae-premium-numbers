/**
 * TikTok Events API proxy — Cloudflare Pages Function.
 *
 * Receives pixel events from the browser, enriches with server-known fields
 * (IP, User-Agent, Cloudflare country, TikTok click ID cookie), hashes PII,
 * and forwards to TikTok Events API at /open_api/v1.3/event/track/.
 *
 * Uses the same event_id that the client pixel sends, so TikTok dedupes the
 * browser + server event into a single signal. The win: when an ad-blocker
 * kills the client pixel (~15% of UAE traffic), the server-side event still
 * reaches TikTok, and TikTok reports 15% higher conversion volume.
 *
 * Env vars (set in Cloudflare Pages dashboard → Settings → Environment
 * variables → Production):
 *   TIKTOK_EVENTS_API_TOKEN   the long-lived Access Token from TikTok Ads
 *                             Manager -> Events -> Events API setup.
 *   TIKTOK_PIXEL_ID           D7J1GQRC77UDQGOITA8G
 *
 * Browser contract:
 *   POST /api/tiktok-event
 *   Content-Type: application/json
 *   Body: {
 *     event:      "Contact" | "ViewContent" | "AddToCart" | ...
 *     event_id:   same id passed to ttq.track() for dedup
 *     page_url:   location.href
 *     page_referrer: document.referrer
 *     user: {                          optional — any omitted will be hashed empty
 *       email, phone, external_id      hashed SHA-256 lowercased before send
 *     },
 *     properties: {                    passes straight through to TikTok
 *       value, currency, content_id, content_type, content_name,
 *       content_category, search_string
 *     }
 *   }
 *   Returns: { ok: true, tiktok: <response> }  on success
 *            { ok: false, error: <msg>, tiktok: <response> }  on failure
 */

const TIKTOK_ENDPOINT = "https://business-api.tiktok.com/open_api/v1.3/event/track/";

async function sha256Hex(input) {
  if (!input) return "";
  const buf = new TextEncoder().encode(String(input).trim().toLowerCase());
  const hash = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("");
}

function getCookie(cookieHeader, name) {
  if (!cookieHeader) return "";
  const m = cookieHeader.match(new RegExp("(?:^|; )" + name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1") + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : "";
}

export async function onRequestPost(ctx) {
  const { request, env } = ctx;
  const corsHeaders = {
    "Access-Control-Allow-Origin": "https://uaepremiumnumbers.com",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
  };

  const token = env.TIKTOK_EVENTS_API_TOKEN;
  const pixelId = env.TIKTOK_PIXEL_ID || "D7J1GQRC77UDQGOITA8G";
  if (!token) {
    return new Response(JSON.stringify({ ok: false, error: "TIKTOK_EVENTS_API_TOKEN env var missing in Cloudflare Pages settings" }), { status: 500, headers: corsHeaders });
  }

  let body;
  try { body = await request.json(); } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: "invalid JSON body" }), { status: 400, headers: corsHeaders });
  }

  const event = body.event;
  const event_id = body.event_id || ("e_" + Date.now() + "_" + Math.random().toString(36).slice(2, 10));
  if (!event) {
    return new Response(JSON.stringify({ ok: false, error: "event field required" }), { status: 400, headers: corsHeaders });
  }

  const userIn = body.user || {};
  const cookieHeader = request.headers.get("Cookie") || "";
  const userHashed = {};
  if (userIn.email)       userHashed.email = await sha256Hex(userIn.email);
  if (userIn.phone)       userHashed.phone = await sha256Hex(userIn.phone);
  if (userIn.external_id) userHashed.external_id = await sha256Hex(userIn.external_id);

  const ip = request.headers.get("CF-Connecting-IP") || request.headers.get("X-Real-IP") || "";
  const ua = request.headers.get("User-Agent") || "";
  const ttclid = userIn.ttclid || getCookie(cookieHeader, "ttclid") || "";
  const ttp = userIn.ttp || getCookie(cookieHeader, "_ttp") || "";

  if (ip)     userHashed.ip = ip;
  if (ua)     userHashed.user_agent = ua;
  if (ttclid) userHashed.ttclid = ttclid;
  if (ttp)    userHashed.ttp = ttp;

  const payload = {
    event_source: "web",
    event_source_id: pixelId,
    data: [{
      event: event,
      event_time: Math.floor(Date.now() / 1000),
      event_id: event_id,
      user: userHashed,
      page: {
        url: body.page_url || "",
        referrer: body.page_referrer || "",
      },
      properties: body.properties || {},
    }],
  };

  try {
    const tiktokResp = await fetch(TIKTOK_ENDPOINT, {
      method: "POST",
      headers: {
        "Access-Token": token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const tiktokJson = await tiktokResp.json().catch(() => ({}));
    const ok = tiktokResp.ok && tiktokJson.code === 0;
    return new Response(JSON.stringify({ ok: ok, event_id: event_id, tiktok: tiktokJson }), { status: ok ? 200 : 502, headers: corsHeaders });
  } catch (err) {
    return new Response(JSON.stringify({ ok: false, error: String(err) }), { status: 502, headers: corsHeaders });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "https://uaepremiumnumbers.com",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
    },
  });
}
