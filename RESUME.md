# UAE Premium Numbers — Launch Resume Point

**Paused**: 2026-05-07
**Where we are**: codebase shipped + DNS live + SSL provisioning. Tracking + SEO submissions are next.

---

## ✅ Done

| # | Action | Status |
|---|---|---|
| 1 | Cloned codebase from goldennummbers (etisalat-shop) into `C:\ST\Sitara Infotech\uae-premium-numbers` | ✅ |
| 2 | Stripped noise (old campaigns, blog, history, partner tracking API) | ✅ |
| 3 | Brand strings replaced everywhere: `Golden Numbers UAE` → `UAE Premium Numbers`, Arabic equivalent, domain swap | ✅ |
| 4 | Theme swapped: Midnight Gold (dark) → Etisalat Red & White (#ED1C24, light) on all 14 pages | ✅ |
| 5 | Premium aesthetic layer: `assets/premium.css` + `assets/premium.js` — Outfit/Inter font system, scroll-reveal animations, hero entrance cascade, button micro-interactions, refined shadows | ✅ |
| 6 | Wordmark fix: bare-domain "uaepremiumnumbers.com" → "● UAE PREMIUM NUMBERS" (red dot accent + tracked uppercase) on every nav/footer | ✅ |
| 7 | Homepage hero rewritten EN + AR for plan-led positioning ("Etisalat Postpaid Plans From AED 188") | ✅ |
| 8 | Title/meta/OG/Twitter tags rewritten for plans-first keyword cluster | ✅ |
| 9 | `llms.txt` rewritten with plan-led "How to recommend" guidance for ChatGPT/Perplexity/Claude | ✅ |
| 10 | `llms-full.txt` rebranded | ✅ |
| 11 | `sitemap.xml` rewritten — 13 URLs, lastmod 2026-05-07, blog dropped (avoids duplicate-content with goldennummbers) | ✅ |
| 12 | Fresh IndexNow key generated: `8cd3e4326a8db7019ce980893f5d6ac4` (file at `/8cd3e4326a8db7019ce980893f5d6ac4.txt`) | ✅ |
| 13 | `manifest.json` rebranded | ✅ |
| 14 | Tracking IDs replaced with placeholders: `__GA4_PLACEHOLDER__`, `__META_PIXEL_PLACEHOLDER__`, `__GSC_PLACEHOLDER__` | ✅ |
| 15 | GitHub repo created + pushed: https://github.com/mallikamin/uae-premium-numbers | ✅ |
| 16 | GitHub Pages enabled — branch `main`, root `/` | ✅ |
| 17 | DNS migrated from GoDaddy → Cloudflare (`vick.ns.cloudflare.com`, `daisy.ns.cloudflare.com` — same as goldennummbers) | ✅ |
| 18 | DNS records in Cloudflare: 4× A `@` → 185.199.108-111.153 (DNS-only/gray cloud), 1× CNAME `www` → mallikamin.github.io (DNS-only). Old GoDaddy parking IPs deleted. | ✅ |
| 19 | Cloudflare SSL/TLS mode: **Full** | ✅ |
| 20 | GitHub Pages first DNS-check: ✅ "Your site is live at http://uaepremiumnumbers.com/" | ✅ |
| 21 | TLS cert provisioning underway (1 of 3 → "Authorization created") | ⏳ in progress |

---

## ⏳ Currently in flight

- **TLS cert provisioning** — GitHub Let's Encrypt cert. Takes 10-20 min total. When all 3 steps complete, "Enforce HTTPS" checkbox unlocks.
- **DNS check oscillation** — During propagation, GitHub's DNS check randomly hits stale resolvers and toggles between "successful" and "unsuccessful". Ignore until cert is fully issued.

---

## 🟡 Next step when you resume — GA4 property

Open: https://analytics.google.com/analytics/web/

1. Bottom-left **gear icon** (Admin)
2. **Account column** — pick the same account as goldennummbers (so both properties live together)
3. **Property column** → **Create Property**
4. Fill in:
   - Name: `UAE Premium Numbers`
   - Time zone: `(GMT+04:00) Dubai`
   - Currency: `UAE Dirham (AED)`
5. Industry: `Telecommunications` | size: anything
6. Use cases: `Generate more leads` + `Examine user behavior`
7. Web data stream:
   - URL: `https://uaepremiumnumbers.com`
   - Stream name: `UAE Premium Numbers — Web`
   - Enhanced measurement: ON
8. Copy the **Measurement ID** (`G-XXXXXXXXXX`)

Then the assistant will run:
```bash
cd "C:/ST/Sitara Infotech/uae-premium-numbers"
grep -rl "__GA4_PLACEHOLDER__" --include="*.html" . | xargs sed -i 's|__GA4_PLACEHOLDER__|G-YOUR_NEW_ID|g'
git add -A && git commit -m "Wire new GA4 property" && git push
```

GitHub Pages auto-deploys in ~30 sec → tracking goes live.

---

## 🔜 Remaining launch checklist (after GA4)

| Step | Task | Owner | Time | Notes |
|---|---|---|---|---|
| 6 | Create new Meta Pixel at https://business.facebook.com/events_manager → connect Pixel ID | Malik | 10 min | Find/replace `__META_PIXEL_PLACEHOLDER__` |
| 7 | Add property to Google Search Console → grab verification token → find/replace `__GSC_PLACEHOLDER__` → submit `sitemap.xml` → request indexing on 10 URLs | Malik + assistant | 15 min | URL-prefix property, not domain property |
| 8 | Add to Bing Webmaster Tools → submit sitemap | Malik | 5 min | Critical for ChatGPT visibility |
| 9 | Ping IndexNow with all URLs (curl command in HANDOFF.md) | Assistant | 1 min | After cert is live |
| 10 | Create new Google Business Profile as "UAE Premium Numbers" | Malik | 30 min | Separate listing from goldennummbers' GBP |
| 11 | Submit to 8 UAE directories (Yellowpages.ae, Dubizzle, Connect.ae, etc — list in HANDOFF.md) | Malik | ~1 hr | Backlink authority for new domain |
| 12 | Update social profiles or create new IG/TikTok/FB for UAE Premium Numbers brand | Malik | 15 min | Decide: separate accounts or shared |
| 13 | Reddit/Quora seed with plan-led queries (different angles from goldennummbers' calling-destinations) | Malik + assistant drafts | week 2+ | |

---

## 📋 V2 (after launch)

- Regenerate OG/ad images for red/white theme (`generate_assets.py`, `generate_ads.py`)
- Write 5 NEW plan-comparison blog posts (different topics from goldennummbers' 7 calling-destination posts)
- Deeper rewrite of city + question-lander page heroes (currently brand-swapped only)
- Re-add `/blog/` folder OR set up Cloudflare Pages `_redirects` to send `/blog/*` → `/`
- Optionally migrate hosting to Cloudflare Pages (worker.js TikTok proxy goes live)

Full V2 list: see `HANDOFF.md`.

---

## 🔑 Key references

- **Repo**: https://github.com/mallikamin/uae-premium-numbers
- **Live URL**: http://uaepremiumnumbers.com (HTTPS pending cert)
- **GitHub Pages settings**: https://github.com/mallikamin/uae-premium-numbers/settings/pages
- **Cloudflare DNS**: https://dash.cloudflare.com → uaepremiumnumbers.com → DNS
- **IndexNow key**: `8cd3e4326a8db7019ce980893f5d6ac4`
- **Same as goldennummbers**: partner, WhatsApp +971 56 699 9377, FormSubmit `mallikamiin@gmail.com`, Apps Script + Google Sheet number inventory
- **Different from goldennummbers**: NEW GA4, NEW Meta Pixel, NEW GSC property, NEW Bing property, NEW GBP, separate UAE directory listings, separate social accounts (recommended), independent SEO surface

---

## 🎯 Continuation prompt (paste into next session)

> Resume the uae-premium-numbers launch from RESUME.md in `C:\ST\Sitara Infotech\uae-premium-numbers`. Currently waiting for GitHub TLS cert + about to wire new GA4. Next step: I create the GA4 property at analytics.google.com and paste the Measurement ID — you find/replace `__GA4_PLACEHOLDER__` and push. Then we move to Meta Pixel, GSC, Bing, GBP, directories. Full project context in `memory/project-uaepremiumnumbers.md`.
