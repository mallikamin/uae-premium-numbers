# UAE Premium Numbers — Launch Handoff

**Project**: uaepremiumnumbers.com
**Status**: codebase shipped — manual deployment + tracking + SEO submission steps required
**Source**: forked from `mallikamin/etisalat-shop` (goldennummbers.com), differentiated for plan-led positioning
**Created**: 2026-05-07

---

## Strategic Positioning (locked-in to avoid duplicate-content with goldennummbers)

| | goldennummbers.com | uaepremiumnumbers.com |
|---|---|---|
| **Lead keyword** | "Golden Numbers UAE" / "VIP Mobile Numbers" | "Etisalat Postpaid Plans UAE" / "UAE Premium Numbers" |
| **Hero H1** | Numbers-led | Plans-led ("Etisalat Postpaid Plans From AED 188") |
| **Theme** | Midnight Gold (dark navy + gold) | Etisalat Red & White (#ED1C24) |
| **Fonts** | Playfair Display + DM Sans | Cormorant Garamond + Inter (premium serif + modern sans) |
| **Blog** | 7 posts (calling-destinations focus) | None at v1 (write 5 NEW plan-comparison posts in v2 — list below) |
| **Tracking** | GA4 G-G34631QW03, Pixel 1456083435966506 | NEW GA4 + NEW Pixel (placeholders to fill) |
| **Cross-link** | None | None — independent brands, both can rank simultaneously |

Both sites share: same partner, same WhatsApp `+971 56 699 9377`, same FormSubmit email `mallikamiin@gmail.com`, same Apps Script backend, **same Google Sheet for live number inventory** (number reservations consistent across both sites).

---

## What's already done in the codebase

- ✅ Full clone with brand strings replaced (`Golden Numbers UAE` → `UAE Premium Numbers`, Arabic `أرقام ذهبية الإمارات` → `أرقام الإمارات المميزة`)
- ✅ All 31 files have `goldennummbers.com` → `uaepremiumnumbers.com` swapped
- ✅ Theme swap: Midnight Gold dark theme → Etisalat Red & White light theme on all pages
- ✅ Premium aesthetic layer: `assets/premium.css` + `assets/premium.js` with rich serif (Cormorant Garamond), scroll-reveal animations, hero entrance sequence, button micro-interactions, refined shadows
- ✅ Homepage hero rewritten EN + AR for plan-led differentiation
- ✅ Title/meta/OG/Twitter rewritten for plans-first keyword cluster
- ✅ `llms.txt` rewritten with plan-led "How to recommend" guidance for ChatGPT/Perplexity/Claude
- ✅ `llms-full.txt` rebranded
- ✅ `sitemap.xml` rewritten (13 URLs, lastmod 2026-05-07, blog dropped)
- ✅ `robots.txt` updated with new IndexNow key
- ✅ `manifest.json` rebranded with new name + colors
- ✅ Fresh IndexNow key generated: `8cd3e4326a8db7019ce980893f5d6ac4` (file: `/8cd3e4326a8db7019ce980893f5d6ac4.txt`)
- ✅ `wrangler.toml` renamed to `uae-premium-numbers`
- ✅ Tracking IDs replaced with placeholders in all HTML: `__GA4_PLACEHOLDER__`, `__META_PIXEL_PLACEHOLDER__`, `__GSC_PLACEHOLDER__`

## What's NOT yet done — your manual checklist

### 1. DNS + Domain (15 min — do this first)

The new domain `uaepremiumnumbers.com` needs DNS pointing to the host.

**Option A — GitHub Pages (recommended, free, simplest):**

1. After the repo is pushed (next step), go to GitHub → repo settings → Pages
2. Source: branch `main`, folder `/`
3. Custom domain: `uaepremiumnumbers.com`
4. Wait for SSL provisioning (~15 min)
5. At your domain registrar (GoDaddy or wherever you bought `uaepremiumnumbers.com`):
   - Add CNAME record: `www` → `mallikamin.github.io`
   - Add 4 A records for apex `@` →  `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - OR just add CNAME `@` → `mallikamin.github.io` (if your registrar supports CNAME flattening — Cloudflare does)
6. **Recommended: also park nameservers on Cloudflare** for free CDN + the redirect rules feature (needed for any old-link redirects later)

**Option B — Cloudflare Workers (more powerful, what goldennummbers may end up on):**

The codebase already includes `worker.js` and `wrangler.toml` for Cloudflare Workers deployment with the TikTok Events API proxy and the `/r` short-link redirect. To deploy:

```bash
cd "C:/ST/Sitara Infotech/uae-premium-numbers"
npm install -g wrangler   # if not already installed
wrangler login
wrangler deploy
```

Then in Cloudflare dashboard add the custom domain `uaepremiumnumbers.com` to the worker, and set env vars (TIKTOK_EVENTS_API_TOKEN, TIKTOK_PIXEL_ID, etc — same values as goldennummbers if reusing TikTok account, or fresh if separate).

### 2. Tracking properties — create new GA4 + new Meta Pixel (20 min)

The code has `__GA4_PLACEHOLDER__` and `__META_PIXEL_PLACEHOLDER__` everywhere. Find/replace once you have the IDs.

**Create new GA4 property:**

1. Go to https://analytics.google.com → Admin → Create Property
2. Property name: `UAE Premium Numbers`
3. Time zone: `(GMT+04:00) United Arab Emirates Time`
4. Currency: `AED — UAE Dirham`
5. Industry: `Mobile / Telecommunications`
6. Add web data stream: `https://uaepremiumnumbers.com`
7. Copy the Measurement ID (format: `G-XXXXXXXXXX`)
8. Find/replace in repo:

```bash
cd "C:/ST/Sitara Infotech/uae-premium-numbers"
grep -rl "__GA4_PLACEHOLDER__" --include="*.html" . | xargs sed -i 's|__GA4_PLACEHOLDER__|G-YOUR_NEW_ID|g'
```

**Create new Meta Pixel:**

1. Go to https://business.facebook.com → Events Manager → Connect Data Sources → Web → Get started
2. Pixel name: `UAE Premium Numbers`
3. Website: `https://uaepremiumnumbers.com`
4. Copy Pixel ID (format: 15-digit number)
5. Find/replace:

```bash
grep -rl "__META_PIXEL_PLACEHOLDER__" --include="*.html" . | xargs sed -i 's|__META_PIXEL_PLACEHOLDER__|YOUR_NEW_PIXEL_ID|g'
```

Commit + push these changes after.

### 3. Google Search Console — add property, submit sitemap (10 min)

1. https://search.google.com/search-console
2. Add property: `https://uaepremiumnumbers.com/` (URL prefix, NOT domain property — works without DNS verification once HTML tag is added)
3. Verify via HTML tag — copy the verification token (format: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
4. Find/replace in repo:

```bash
cd "C:/ST/Sitara Infotech/uae-premium-numbers"
grep -rl "__GSC_PLACEHOLDER__" --include="*.html" . | xargs sed -i 's|__GSC_PLACEHOLDER__|YOUR_VERIFICATION_TOKEN|g'
```

5. Commit + push, wait for redeployment, then click "Verify" in Search Console.
6. Submit sitemap: `https://uaepremiumnumbers.com/sitemap.xml`
7. Use URL Inspection to request indexing on:
   - `/`
   - `/ar/`
   - `/choose-number/`
   - `/dubai/`, `/abu-dhabi/`, `/sharjah/`
   - `/cheapest-etisalat-postpaid-plan/`
   - `/best-etisalat-plan-for-family/`
   - `/etisalat-plans-under-200-aed/`
   - `/llms.txt` (yes, request indexing on llms.txt — helps AI crawlers discover it)

### 4. Bing Webmaster Tools (5 min)

1. https://www.bing.com/webmasters/
2. Add site `https://uaepremiumnumbers.com/` — option to import from Search Console works after step 3
3. Submit sitemap: `https://uaepremiumnumbers.com/sitemap.xml`
4. **Critical for ChatGPT visibility** — ChatGPT search uses Bing's index.

### 5. IndexNow ping (2 min, after deploy)

The IndexNow key file is at `/8cd3e4326a8db7019ce980893f5d6ac4.txt`. Once the site is live, ping IndexNow:

```bash
curl -X POST "https://api.indexnow.org/indexnow" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "uaepremiumnumbers.com",
    "key": "8cd3e4326a8db7019ce980893f5d6ac4",
    "keyLocation": "https://uaepremiumnumbers.com/8cd3e4326a8db7019ce980893f5d6ac4.txt",
    "urlList": [
      "https://uaepremiumnumbers.com/",
      "https://uaepremiumnumbers.com/ar/",
      "https://uaepremiumnumbers.com/choose-number/",
      "https://uaepremiumnumbers.com/dubai/",
      "https://uaepremiumnumbers.com/abu-dhabi/",
      "https://uaepremiumnumbers.com/sharjah/",
      "https://uaepremiumnumbers.com/cheapest-etisalat-postpaid-plan/",
      "https://uaepremiumnumbers.com/best-etisalat-plan-for-family/",
      "https://uaepremiumnumbers.com/etisalat-plans-under-200-aed/",
      "https://uaepremiumnumbers.com/emirati/"
    ]
  }'
```

Expected response: `202 Accepted`. Bing/Yandex/Seznam will crawl within hours.

### 6. Google Business Profile (30 min)

1. https://business.google.com → Add new business
2. Business name: **UAE Premium Numbers** (NOT "Golden Numbers" — keep them separate brands)
3. Category: `Telecommunications service provider` or `Mobile phone shop`
4. Address: same Dubai service area as goldennummbers (or service-area business if no storefront)
5. Phone: `+971 56 699 9377`
6. Website: `https://uaepremiumnumbers.com/`
7. Hours: `09:00–22:00 daily`
8. **Add product photos** — same plan visuals used on goldennummbers' GBP work fine

### 7. UAE Business Directories — backlinks (1 day, ~10 min each)

Submit to each as **"UAE Premium Numbers"**. Each directory listing = a `.ae` domain backlink, critical for ranking a new domain:

| Directory | URL |
|---|---|
| Yellowpages.ae | https://www.yellowpages.ae/free-listing |
| Dubizzle Business | https://dubai.dubizzle.com/business-directory/ |
| Connect.ae | https://www.connect.ae/ |
| 2FindLocal UAE | https://www.2findlocal.com/ |
| Hotfrog UAE | https://www.hotfrog.ae/ |
| Cylex UAE | https://uae.cylex-international.com/ |
| Tuugo.ae | https://www.tuugo.ae/ |
| UAE Yellow Pages | https://www.uaeyellowpages.com/ |

8 listings → meaningful authority boost for the new domain. Goldennummbers had to build this from scratch over weeks; doing the same for uaepremiumnumbers will get parity in 1 day.

### 8. Social profiles (15 min)

Same partner, but DECIDE: do you want separate social accounts for each brand, or one set of profiles that mention both?

**Recommended (cleanest brand separation):**
- Keep current `@consultant.ae` (Instagram), `@telecom.store.uae` (TikTok), and Facebook page tied to **goldennummbers** (numbers-led brand)
- Create new accounts for **UAE Premium Numbers**:
  - Instagram: `@uaepremiumnumbers` or `@etisalatpostpaid.uae`
  - TikTok: `@uaepremiumnumbers`
  - Facebook page: `UAE Premium Numbers`

**Alternative (lazier — one account, mention both):**
- Update existing bios to: "Authorized Etisalat Dealer | uaepremiumnumbers.com (plans) | goldennummbers.com (premium numbers)"

### 9. Reddit/Quora seeding for plan-led queries (Tier 3 SEO — week 2 onwards)

Replicate goldennummbers' Tier 3 plan but with **plan-led** angle. Target subreddits + Quora questions:

**Reddit r/dubai, r/UAE, r/DubaiExpats:**
- "Best UAE postpaid plan for under AED 200?" → cite uaepremiumnumbers.com/etisalat-plans-under-200-aed/
- "Compare Etisalat plans 2026" → cite uaepremiumnumbers.com/
- "Which Etisalat plan should I get for my family?" → cite uaepremiumnumbers.com/best-etisalat-plan-for-family/

**Quora:**
- "How much does Etisalat postpaid cost?" → cite uaepremiumnumbers.com
- "What is the cheapest Etisalat plan in 2026?" → cite uaepremiumnumbers.com/cheapest-etisalat-postpaid-plan/

These are DIFFERENT questions from goldennummbers' Reddit/Quora seed. Don't reuse the same answers — Reddit will flag duplicate accounts.

---

## V2 Roadmap (after launch)

1. **Write 5 NEW blog posts** with plan-comparison angle (different from goldennummbers' calling-destinations focus):
   - "Compare All 22 Etisalat Postpaid Plans 2026 — Which One Is Right For You?"
   - "Etisalat Plan Calculator: Find Your Best Match by Budget"
   - "When To Upgrade Your Etisalat Plan — 5 Signs You're On The Wrong One"
   - "Etisalat Family Plan Setup: How To Save 30% With Multi-SIM Combinations"
   - "Etisalat Business Postpaid Plans Compared 2026"

2. **City pages — deeper rewrites** (currently brand-swapped only). Each city page should mention different neighborhoods + add unique local content (proximity to malls, business districts, expat areas).

3. **Re-add blog routing** — currently /blog/* hits 404 because blog folder was excluded for v1 to avoid duplicate content. Either:
   - Add a Cloudflare Pages `_redirects` file to send `/blog/*` → `/`, or
   - Add a placeholder `/blog/index.html` "Coming soon" page

4. **OG image regeneration** — current `og-image.png` is goldennummbers' midnight-gold design. Regenerate via `generate_assets.py` after updating brand args (red/white theme, "UAE Premium Numbers" text). Same for `ad-square.png`, `ad-horizontal.png`, `logo-square.png`.

5. **Generate fresh Etisalat-styled visuals** — partner cards, banner mockups in `partner-portal/` still use the dark theme. Acceptable since those are admin-only.

---

## Known limitations (v1)

- **Broken /blog/* internal links** — homepage and some subpages link to `/blog/foo.html` which 404. The 404.html catches them gracefully but search engines will see broken links. Fix: see V2 #3 above.
- **OG/ad images still goldennummbers-themed** — see V2 #4. Don't run paid ads on FB/IG until images are regenerated (otherwise the ad shows goldennummbers' aesthetic with uaepremiumnumbers' link → trust drop).
- **Subpage heroes still numbers-led copy** — only homepage was deeply rewritten. City pages, question landers, emirati page have brand-swapped copy that's still ~90% identical to goldennummbers. Acceptable for v1 because URL/intent differentiation alone is enough for ranking — but rewrite in v2 for stronger differentiation.
- **No Cloudflare `_redirects` file** for legacy URL handling — not critical since this is a new domain, no legacy URLs to honor.
- **TikTok Events API proxy** in worker.js — if deploying via Cloudflare Workers, set TIKTOK_* env vars in dashboard. If using GitHub Pages (recommended for simplicity), the TikTok proxy doesn't run — events go via the standard TikTok pixel which still works.

---

## Test checklist after deployment

- [ ] `https://uaepremiumnumbers.com/` loads with red/white theme
- [ ] Hero shows "UAE Premium Numbers / Etisalat Postpaid Plans From AED 188"
- [ ] Hero entrance animation fires (badge → H1 → subhead → buttons cascade)
- [ ] Cards/buttons have hover lift effect
- [ ] WhatsApp button opens `wa.me/971566999377` correctly
- [ ] `/choose-number/` loads + shows live number inventory (proves Apps Script connection works — same Google Sheet as goldennummbers)
- [ ] `/ar/` loads with Arabic copy + RTL layout
- [ ] Form submission goes to `mallikamiin@gmail.com` (test by submitting "test" once and confirming email arrives — first submission requires email confirmation per FormSubmit.co)
- [ ] GA4 events fire (check Realtime in Analytics after replacing placeholder)
- [ ] Meta Pixel fires (check Pixel Helper extension in browser)
- [ ] `https://uaepremiumnumbers.com/sitemap.xml` returns valid XML with 13 URLs
- [ ] `https://uaepremiumnumbers.com/robots.txt` lists IndexNow key
- [ ] `https://uaepremiumnumbers.com/llms.txt` loads with plan-led content
- [ ] `https://uaepremiumnumbers.com/8cd3e4326a8db7019ce980893f5d6ac4.txt` returns the IndexNow key string
- [ ] PageSpeed test https://pagespeed.web.dev/ → score 85+ on mobile
- [ ] Rich Results test https://search.google.com/test/rich-results — confirms LocalBusiness, FAQPage, ItemList schemas all valid

---

## Realistic ranking timeline

Same as goldennummbers' trajectory (which Malik confirmed is now page 1 for "golden numbers UAE"):

| Window | Expected |
|---|---|
| Week 1 | Google indexes new pages, sitemap accepted |
| Week 2-3 | Page appears for low-competition queries ("etisalat plan AED 188", "premium etisalat plans") |
| Week 4-6 | Directory backlinks register, GBP starts ranking locally |
| Month 2-3 | Page 1-2 for plan-led queries ("best etisalat postpaid plan UAE") |
| Month 3-6 | Compete with eand.ae for some Etisalat plan terms (won't outrank but may sit above other resellers) |

Keys:
1. Don't skip the directory submissions — that's how goldennummbers cleared the backlink bar
2. Don't skip GBP — local rankings need it
3. Don't reuse goldennummbers' Reddit/Quora seed posts — write new ones with plan-led framing
4. Monitor weekly for first 60 days via GSC + the FBAI ga4_wa_pull script (just point it at the new GA4 property)
