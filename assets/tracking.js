/**
 * uaepremiumnumbers.com unified tracking helper.
 * Centralizes GA4 + Meta Pixel + TikTok Pixel events with deduplication event_id.
 * Loaded on every page after gtag/fbq/ttq init scripts.
 *
 * Functions:
 *   GN.genEventId()                                    → unique id for pixel/GA4/CAPI dedup
 *   GN.trackWhatsAppClick(ctx, pageContext)            → every wa.me click
 *   GN.trackNumberInquiry({number, category, ref, leadToken})  → /choose-number wa clicks
 *   GN.trackLead({source, interest, value})            → form submits, signups
 *   GN.trackPartnerScan(refCode)                       → QR partner scans
 */
(function () {
  'use strict';
  var PIXEL_ID = '__META_PIXEL_PLACEHOLDER__';
  var PIXEL_VALUE = 500; // avg AED per lead — used for pixel attribution weighting
  var CURRENCY = 'AED';

  function genEventId() {
    return 'e_' + Date.now() + '_' + Math.random().toString(36).slice(2, 10);
  }

  function createLeadTokenShort() {
    // 7-char uppercase token — used inside the WA Ref: suffix Bilal reads
    return Math.random().toString(36).slice(2, 6).toUpperCase() + Date.now().toString(36).slice(-3).toUpperCase();
  }

  function safe(s, max) {
    if (s == null) return '';
    return String(s).trim().substring(0, max || 100);
  }

  /* ========================================
     TRAFFIC SOURCE ATTRIBUTION
     ========================================
     Classifies every visitor as Organic (O) or Performance Marketing (PM),
     then by channel. Last-touch per session, sessionStorage-cached.
  */
  function extractCampaignTag(utmCampaign) {
    var clean = String(utmCampaign || '').replace(/[^a-zA-Z0-9]/g, '');
    if (!clean) return '';
    // Numeric-only = likely Meta/Google campaign ID -> last 6 chars (most entropic)
    if (/^\d+$/.test(clean)) return clean.slice(-6).toUpperCase();
    // Alphanumeric = human-named campaign -> first 8 chars
    return clean.slice(0, 8).toUpperCase();
  }

  function detectTrafficSource() {
    var p;
    try { p = new URLSearchParams(window.location.search || ''); } catch (e) { p = null; }
    function q(k) { try { return p && p.get(k) || ''; } catch (e) { return ''; } }

    var campaign = extractCampaignTag(q('utm_campaign'));
    var utmSource = q('utm_source').toLowerCase();
    var partner = (q('ref') || '').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 15).toUpperCase();

    // PAID — click IDs are highest-signal
    if (q('fbclid') || /^(facebook|instagram|fb|ig|meta)$/.test(utmSource)) {
      return { cls: 'PM', ch: 'FB', campaign: campaign, partner: partner };
    }
    if (q('gclid') || q('gbraid') || q('wbraid') || /^(google|adwords|gads)$/.test(utmSource)) {
      return { cls: 'PM', ch: 'GOOG', campaign: campaign, partner: partner };
    }
    if (q('ttclid') || /^(tiktok|tt)$/.test(utmSource)) {
      return { cls: 'PM', ch: 'TIKTOK', campaign: campaign, partner: partner };
    }
    if (q('msclkid') || /^(bing|microsoft)$/.test(utmSource)) {
      return { cls: 'PM', ch: 'BING', campaign: campaign, partner: partner };
    }
    if (utmSource && !/^(organic|direct|referral|email|rss)$/.test(utmSource)) {
      return { cls: 'PM', ch: utmSource.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 8), campaign: campaign, partner: partner };
    }

    // ORGANIC — classify by referrer hostname
    var refHost = '';
    try { refHost = (new URL(document.referrer || '')).hostname.toLowerCase(); } catch (e) {}
    if (!refHost || refHost === window.location.hostname) return { cls: 'O', ch: 'DIRECT', campaign: '', partner: partner };

    if (/(^|\.)google\./.test(refHost))     return { cls: 'O', ch: 'SEO', campaign: 'GOOGLE', partner: partner };
    if (/(^|\.)bing\./.test(refHost))       return { cls: 'O', ch: 'SEO', campaign: 'BING', partner: partner };
    if (/(^|\.)duckduckgo\./.test(refHost)) return { cls: 'O', ch: 'SEO', campaign: 'DDG', partner: partner };
    if (/(^|\.)yahoo\./.test(refHost))      return { cls: 'O', ch: 'SEO', campaign: 'YAHOO', partner: partner };
    if (/(^|\.)yandex\./.test(refHost))     return { cls: 'O', ch: 'SEO', campaign: 'YANDEX', partner: partner };

    if (/chatgpt\.com|openai\.com/.test(refHost))      return { cls: 'O', ch: 'AI', campaign: 'CHATGPT', partner: partner };
    if (/perplexity\.ai/.test(refHost))                return { cls: 'O', ch: 'AI', campaign: 'PPLX', partner: partner };
    if (/claude\.ai|anthropic\.com/.test(refHost))     return { cls: 'O', ch: 'AI', campaign: 'CLAUDE', partner: partner };
    if (/copilot\.microsoft\.com|bing\.com\/chat/.test(refHost)) return { cls: 'O', ch: 'AI', campaign: 'COPILOT', partner: partner };
    if (/gemini\.google\.com|bard\.google\.com/.test(refHost))   return { cls: 'O', ch: 'AI', campaign: 'GEMINI', partner: partner };

    if (/facebook\.com|fb\.com/.test(refHost))   return { cls: 'O', ch: 'SOCIAL', campaign: 'FB', partner: partner };
    if (/instagram\.com/.test(refHost))          return { cls: 'O', ch: 'SOCIAL', campaign: 'IG', partner: partner };
    if (/linkedin\.com/.test(refHost))           return { cls: 'O', ch: 'SOCIAL', campaign: 'LNKD', partner: partner };
    if (/(^|\.)x\.com|twitter\.com/.test(refHost)) return { cls: 'O', ch: 'SOCIAL', campaign: 'X', partner: partner };
    if (/tiktok\.com/.test(refHost))             return { cls: 'O', ch: 'SOCIAL', campaign: 'TIKTOK', partner: partner };
    if (/reddit\.com/.test(refHost))             return { cls: 'O', ch: 'SOCIAL', campaign: 'REDDIT', partner: partner };
    if (/youtube\.com|youtu\.be/.test(refHost))  return { cls: 'O', ch: 'SOCIAL', campaign: 'YT', partner: partner };

    return { cls: 'O', ch: 'REFERRAL', campaign: refHost.replace(/^www\./, '').split('.')[0].toUpperCase().slice(0, 10), partner: partner };
  }

  function getTrafficSource() {
    try {
      var cached = sessionStorage.getItem('gn_traffic_src');
      if (cached) {
        var parsed = JSON.parse(cached);
        if (parsed && parsed.cls) return parsed;
      }
    } catch (e) {}
    var src = detectTrafficSource();
    try { sessionStorage.setItem('gn_traffic_src', JSON.stringify(src)); } catch (e) {}
    return src;
  }

  /* Ref code canonical format (v1) — always 7 dash-separated fields.
     GN1 - <CLS> - <CH> - <CAMPAIGN> - <PARTNER> - <SOURCE> - <TOKEN>
       GN1      version prefix (bumps on format change, enables forward-compat parsing)
       CLS      O | PM
       CH       FB | GOOG | TIKTOK | BING | SEO | AI | SOCIAL | DIRECT | REFERRAL | <OTHER>
       CAMPAIGN last-6 of numeric campaign ID / first-8 of named campaign / SEO engine / AI brand / social brand / X
       PARTNER  SHOP code from ?ref= param, or X
       SOURCE   CTA origin: HERO, MIDPAGE, FAB, FOOTER, CARD<DIGITS>, FORM, etc.
       TOKEN    7-char uppercase unique id

     Parse in Python:
       parts = ref.split('-')  # always 7 items for GN1
       [version, cls, ch, campaign, partner, source, token] = parts
  */
  function buildRefCode(source, leadToken) {
    var src = getTrafficSource();
    var cleanSrc = String(source || 'CTA').toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 20) || 'CTA';
    return [
      'GN1',
      src.cls || 'O',
      src.ch || 'DIRECT',
      src.campaign || 'X',
      src.partner || 'X',
      cleanSrc,
      leadToken
    ].join('-');
  }

  // Server-side CAPI forward — POSTs the same event to our Cloudflare Pages
  // Function at /api/tiktok-event, which hashes PII and forwards to TikTok
  // Events API. TikTok dedupes with the client pixel via event_id.
  // Fire-and-forget — never blocks user navigation.
  function forwardToTikTokCapi(eventName, eventId, source, properties) {
    try {
      if (typeof fetch !== 'function') return;
      var payload = {
        event: eventName,
        event_id: eventId,
        page_url: (typeof location !== 'undefined') ? location.href : '',
        page_referrer: (typeof document !== 'undefined') ? document.referrer : '',
        properties: properties || {},
      };
      // keepalive=true so the request survives page unload (critical for
      // WA clicks that immediately navigate away)
      fetch('/api/tiktok-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(function () {});
    } catch (e) {}
  }

  // Rewrites an <a href="wa.me/..."> link to append the Ref: suffix before nav.
  // Also fires TikTok vertical funnel events (AddToCart + InitiateCheckout) so
  // the pixel reports all 6 funnel steps TikTok optimizer expects. Same event_id
  // is used for the server-side CAPI call so TikTok dedupes the pair.
  // Returns the lead token so the caller can use it as eventID for pixel dedup.
  function rewriteWaHref(link, sourceCtx) {
    // 2026-07-24 IDEMPOTENCY GUARD (ported from goldennummbers 0af1dad3). A link
    // may now be reached twice: once by the global auto-wire below, once by a
    // page's own delegated handler (index.html has one). Without this the Ref:
    // suffix is appended twice AND the TikTok AddToCart/InitiateCheckout/Contact
    // trio fires twice per click. Whichever call lands first does the work; the
    // second returns the same token so callers using it as a pixel dedup eventID
    // stay consistent.
    try {
      var prior = link.getAttribute('data-upn-token');
      if (prior) return prior;
    } catch (e) {}

    var leadToken = createLeadTokenShort();
    var source = sourceCtx || link.getAttribute('data-cta') || (link.textContent || '').trim().slice(0, 30);
    try {
      var href = link.getAttribute('href') || '';
      var qIdx = href.indexOf('?text=');
      var base = qIdx >= 0 ? href.substring(0, qIdx) : href;
      var existing = qIdx >= 0
        ? decodeURIComponent(href.substring(qIdx + 6))
        : 'Hi, I\'m interested in an Etisalat VIP number from uaepremiumnumbers.com';
      var tracked = existing + '\n\nRef: ' + buildRefCode(source, leadToken);
      link.setAttribute('href', base + '?text=' + encodeURIComponent(tracked));
    } catch (e) {}

    var valueProps = {
      content_name: 'WA CTA Click',
      content_category: source,
      content_type: 'product',
      value: PIXEL_VALUE,
      currency: CURRENCY
    };

    // Client-side pixel events (visible in browser)
    if (typeof ttq !== 'undefined' && ttq.track) {
      try {
        ttq.track('AddToCart', valueProps);
        ttq.track('InitiateCheckout', { content_name: 'WhatsApp Conversation Initiated', content_category: source, value: PIXEL_VALUE, currency: CURRENCY });
      } catch (e) {}
    }

    // Server-side CAPI mirror for ad-blocker resilience + 15% CPA uplift
    forwardToTikTokCapi('AddToCart', leadToken, source, valueProps);
    forwardToTikTokCapi('InitiateCheckout', leadToken, source, { content_name: 'WhatsApp Conversation Initiated', value: PIXEL_VALUE, currency: CURRENCY });
    forwardToTikTokCapi('Contact', leadToken, source, { content_name: 'WhatsApp Click', value: PIXEL_VALUE, currency: CURRENCY });

    try { link.setAttribute('data-upn-token', leadToken); } catch (e) {}
    return leadToken;
  }

  function normalizePhone(raw) {
    if (!raw) return '';
    var digits = String(raw).replace(/[^0-9]/g, '');
    if (!digits) return '';
    if (digits.charAt(0) === '0') digits = '971' + digits.slice(1);
    if (digits.length === 9) digits = '971' + digits;
    return digits;
  }

  function splitName(full) {
    if (!full) return { fn: '', ln: '' };
    var parts = String(full).trim().split(/\s+/);
    return { fn: (parts[0] || '').toLowerCase(), ln: (parts.slice(1).join(' ') || '').toLowerCase() };
  }

  /**
   * Manual Advanced Matching — enriches the pixel with hashed user identity
   * so Meta can match events to user accounts (improves match rate 20-30%).
   * Call this BEFORE firing a pixel event (e.g., on form submit) with whatever
   * identity fields you have. Meta auto-hashes client-side via SHA-256.
   * Pass any subset of {email, phone, name, city, country, zip, gender, dob, externalId}.
   */
  function setUserIdentity(opts) {
    opts = opts || {};
    if (typeof fbq !== 'function') return;
    var data = {};
    if (opts.email)   data.em = String(opts.email).trim().toLowerCase();
    if (opts.phone)   data.ph = normalizePhone(opts.phone);
    if (opts.name) {
      var n = splitName(opts.name);
      if (n.fn) data.fn = n.fn;
      if (n.ln) data.ln = n.ln;
    }
    if (opts.firstName) data.fn = String(opts.firstName).trim().toLowerCase();
    if (opts.lastName)  data.ln = String(opts.lastName).trim().toLowerCase();
    if (opts.city)      data.ct = String(opts.city).trim().toLowerCase().replace(/\s+/g, '');
    if (opts.country)   data.country = String(opts.country).trim().toLowerCase();
    if (opts.zip)       data.zp = String(opts.zip).trim();
    if (opts.gender)    data.ge = String(opts.gender).charAt(0).toLowerCase();
    if (opts.dob)       data.db = String(opts.dob).replace(/[^0-9]/g, '').slice(0, 8);
    if (opts.externalId) data.external_id = String(opts.externalId);
    if (!Object.keys(data).length) return;
    try { fbq('init', PIXEL_ID, data); } catch (e) {}
  }

  function trackWhatsAppClick(ctx, pageContext) {
    var eid = genEventId();
    var category = safe(ctx, 50) || 'cta';
    var page = safe(pageContext, 50) || (typeof location !== 'undefined' ? location.pathname : '');
    if (typeof fbq === 'function') {
      fbq('track', 'Contact', {
        content_name: 'WhatsApp Click',
        content_category: category,
        value: PIXEL_VALUE,
        currency: CURRENCY
      }, { eventID: eid });
    }
    if (typeof ttq !== 'undefined' && ttq.track) {
      ttq.track('Contact', {
        content_name: 'WhatsApp Click',
        content_category: category
      });
    }
    if (typeof gtag === 'function') {
      gtag('event', 'contact', {
        cta_context: category,
        page_context: page,
        event_id: eid
      });
    }
    return eid;
  }

  function trackNumberInquiry(opts) {
    opts = opts || {};
    var num = safe(opts.number, 30);
    var cat = safe(opts.category, 20) || 'unknown';
    var ref = safe(opts.ref, 30);
    var eid = opts.leadToken || genEventId();
    if (typeof fbq === 'function') {
      fbq('track', 'Contact', {
        content_name: 'Number Inquiry',
        content_category: cat,
        content_ids: [num],
        value: PIXEL_VALUE,
        currency: CURRENCY
      }, { eventID: eid });
    }
    if (typeof ttq !== 'undefined' && ttq.track) {
      ttq.track('Contact', {
        content_name: 'Number Inquiry',
        content_category: cat,
        content_ids: [num]
      });
    }
    if (typeof gtag === 'function') {
      gtag('event', 'number_inquiry', {
        number_id: num,
        number_category: cat,
        ref_code: ref,
        lead_token: eid,
        event_id: eid
      });
    }
    return eid;
  }

  function trackLead(opts) {
    opts = opts || {};
    var source = safe(opts.source, 30) || 'unknown';
    var interest = safe(opts.interest, 50);
    var eid = opts.eventId || genEventId();
    var value = opts.value || PIXEL_VALUE;
    if (typeof fbq === 'function') {
      fbq('track', 'Lead', {
        content_name: source,
        content_category: interest,
        value: value,
        currency: CURRENCY
      }, { eventID: eid });
    }
    if (typeof ttq !== 'undefined' && ttq.track) {
      ttq.track('SubmitForm', {
        content_name: source,
        content_category: interest
      });
    }
    if (typeof gtag === 'function') {
      gtag('event', 'generate_lead', {
        lead_source: source,
        interest_type: interest,
        value: value,
        currency: CURRENCY,
        event_id: eid
      });
    }
    return eid;
  }

  function trackPartnerScan(refCode) {
    var ref = safe(refCode, 30);
    var eid = genEventId();
    if (typeof gtag === 'function') {
      gtag('event', 'partner_scan', {
        ref_code: ref,
        event_id: eid
      });
    }
    if (typeof fbq === 'function') {
      fbq('trackCustom', 'PartnerScan', { ref_code: ref }, { eventID: eid });
    }
    return eid;
  }

  window.GN = {
    genEventId: genEventId,
    createLeadTokenShort: createLeadTokenShort,
    trackWhatsAppClick: trackWhatsAppClick,
    trackNumberInquiry: trackNumberInquiry,
    trackLead: trackLead,
    trackPartnerScan: trackPartnerScan,
    setUserIdentity: setUserIdentity,
    getTrafficSource: getTrafficSource,
    buildRefCode: buildRefCode,
    rewriteWaHref: rewriteWaHref,
    forwardToTikTokCapi: forwardToTikTokCapi,
    VALUE: PIXEL_VALUE,
    CURRENCY: CURRENCY,
    PIXEL_ID: PIXEL_ID
  };

  // Fire server-side ViewContent on page load so TikTok sees it even when
  // ad-blockers nuke the client pixel. Uses a fresh event_id (different
  // from any click events) since ViewContent is a standalone signal.
  function fireViewContentCapi() {
    var eid = genEventId();
    var title = (typeof document !== 'undefined' && document.title) ? document.title.slice(0, 80) : '';
    var path = (typeof location !== 'undefined') ? location.pathname : '';
    forwardToTikTokCapi('ViewContent', eid, 'pageload', {
      content_name: title,
      content_category: path,
      content_type: 'product_group',
      content_id: path,
    });
  }
  if (typeof document !== 'undefined') {
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      setTimeout(fireViewContentCapi, 100);
    } else {
      document.addEventListener('DOMContentLoaded', fireViewContentCapi);
    }
  }

  // ---------------------------------------------------------------------------
  // 2026-07-24 GLOBAL WA AUTO-WIRE (ported from goldennummbers 0af1dad3).
  // rewriteWaHref was only ever invoked explicitly, and only index.html did it.
  // Every plan, eSIM, area and /numbers/ page either loaded this script and never
  // called it, or never loaded it at all, so their WhatsApp clicks reached the
  // CRM with no Ref. This binds the same delegated-click pattern index.html
  // already proves works, for every page that loads tracking.js.
  // Click-time, not load-time, on purpose: rewriteWaHref fires the TikTok
  // AddToCart/InitiateCheckout/Contact trio, so wiring at load would emit one
  // fake funnel event per wa.me link per pageview.
  function autoWaSource(link) {
    var explicit = link.getAttribute('data-cta');
    if (explicit) return explicit;
    var path = (typeof location !== 'undefined' && location.pathname) || '';
    // /numbers/etisalat-0541655100/ -> CARD0541655100, so the MSISDN survives the
    // WhatsApp handoff and the sale is traceable back to the exact number page.
    var card = path.match(/\/numbers\/etisalat-(\d{10})/);
    if (card) return 'CARD' + card[1];
    var slug = path.replace(/^\/+|\/+$/g, '').split('/').pop() || 'HOME';
    return slug.replace(/\.html?$/, '').slice(0, 20) || 'HOME';
  }

  function onWaClick(ev) {
    var t = ev && ev.target;
    if (!t || typeof t.closest !== 'function') return;
    var link = t.closest('a[href*="wa.me"]');
    if (!link) return;
    // Synchronous: the href is rewritten before the browser follows the link
    // (same pattern index.html already proves works). Fires only on a real
    // click/auxclick, so no pixel inflation from cancelled presses.
    try { rewriteWaHref(link, autoWaSource(link)); } catch (e) {}
  }

  if (typeof document !== 'undefined' && document.addEventListener) {
    // click = left-click, keyboard activation, and mobile tap.
    // auxclick = middle-click / open-in-new-tab.
    // A page with its own handler (index.html) is harmless: the data-upn-token
    // guard in rewriteWaHref makes the second call a no-op returning the same token.
    document.addEventListener('click', onWaClick);
    document.addEventListener('auxclick', onWaClick);
  }
})();
