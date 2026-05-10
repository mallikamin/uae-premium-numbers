# Pause Checkpoint — 2026-05-10

## Project
- **Name**: uae-premium-numbers (UPN) — second brand sibling to goldennummbers (GN)
- **Path**: `C:\ST\Sitara Infotech\uae-premium-numbers`
- **Branch**: `main` (origin: `git@github.com:mallikamin/uae-premium-numbers.git`)
- **Edge**: `loom-edge-01@100.87.222.110` — `/opt/meta-poster-upn/`
- **Live site**: https://uaepremiumnumbers.com

## Goal
Set up UPN as a fully separate brand from goldennummbers — own FB Page, own IG, own TikTok, own YouTube, own automation pipeline — and post 150 plan-led number cards over 10 days to the new FB Page. Both brands share the same Meta App "AI Sync" (App ID `1152633793482968`) and (when YT comes online) the same GCP project `goldennumbers-youtube`, so volume / reputation has to be respected across them.

## Completed (this session, 2026-05-10)
- [x] **FB Page admin** — Bilal's "Golden Numbers UAE" BM (`1025390870648337`) added Sitara Infotech BM as Partner with Full Control
- [x] **Long-lived FB Page Access Token** — generated via Graph API Explorer using AI Sync app, stored at `/opt/meta-poster-upn/config.json` (mode 600). Token verified by `/me` round-trip; first manual test post live: https://www.facebook.com/969170162937075/posts/122130548763164173
- [x] **Website wire** — replaced old `facebook.com/share/17heRMZa83/` with `facebook.com/969170162937075` across 7 files (footer + JSON-LD `sameAs` + llms.txt). Committed `674c9bb`, pushed.
- [x] **Phase 1 — runtime/ foundation** — cloned `meta_poster.py` + `notify.py` from goldennummbers/runtime/. Adaptations: env-driven `BASE_DIR`/`CONFIG`, fcntl Windows-safe, BOM-tolerant config loader, `[uaepremiumnumbers]` email tag. Smoke-tested locally + on edge.
- [x] **Phase 2 — single card renderer** — `make_card.py` red/white plan-led layout (Etisalat red ribbons, white bg, hero number, tier pill, AED 188/MO plan tag, QR + WhatsApp footer). Different from GN's midnight-gold cards. Approved by Malik.
- [x] **Phase 2.b — grid card renderer** — `make_grid_card.py` 3 brand variants (`uaepremiumnumbers` / `premium_etisalat` / `golden_numbers_uae`). 6 numbers in 2×3 light cells with red left-stripe, red price box, red CTA pill. Approved by Malik.
- [x] **Phase 3a — daily_generator mechanical adapt** — counts (5 single + 10 grid/day), paths (`/opt/meta-poster-upn`), URLs (`uaepremiumnumbers.com/cards/`, `uaepremiumnumbers.com/choose-number/`), brand string, ID prefix `upn-`.
- [x] **Phase 3b — captions plan-led** — FB_OPENERS, IG_OPENERS, GRID_FB_OPENERS, GRID_IG_OPENERS rewritten to lead with the Etisalat plan + AED 188/mo. New hashtag pools: `#UAEPremiumNumbers` `#EtisalatPostpaid` `#EtisalatPlans`.
- [x] **Phase 3c — cross-brand dedupe** — `load_used_digits()` reads UPN's archive/+approved/ AND GN's archive/+approved/ via `GN_DEDUP_PATHS`. Honors both `digits` (singles) and `digits_list` (grids).
- [x] **Phase 3d — production fixes** — INTERVAL_MIN 100 (was 96), first-run anchor `2026-05-10 20:30 PKT`, `_avoid_gn_collisions()` enforces ≥30-min gap from any GN slot. `push_cards()` re-run-safe (skips commit when no diff).
- [x] **Email policy** — removed Daily plan + Batch completion summary emails per Malik's "no spam" rule. Only per-post success / per-post failure / sheet-exhausted / crashed emails fire.
- [x] **Phase 4 — edge deploy** — `/opt/meta-poster-upn/` cloned + venv (requests, Pillow, qrcode), config.json with token, cron `7-59/15 * * * *` armed (offset 7 min from GN's `*/15`).
- [x] **Phase 5 — 150-post queue** — 10 manual `daily_generator.py --force` runs scheduled 150 posts spanning **2026-05-10 21:18 PKT → 2026-05-21 14:58 PKT**. All cards rendered + pushed to GitHub Pages (HTTP 200 verified).
- [x] **Hotfix #1 (IG null skip)** — meta_poster.py crashed on `cfg.ig_user_id=null` (UPN IG isn't linked yet). Patched to skip IG silently when null. upn-009 was first casualty: FB posted at 21:22, IG step crashed twice → breaker tripped. Repaired post + cleared breaker. Commit `e5168d4`.
- [x] **Hotfix #2 (YT marker)** — Success email inherited GN's `_yt_status_marker` showing "YT ⏳ queued" for UPN even though no YT cron exists. Patched: `HAS_YOUTUBE = os.path.exists(BASE_DIR/youtube_config.json)` → returns `''` when False. Commit `36b22a8`.
- [x] **First two production posts live**: `upn-009` (056 prefix Gold, 21:22 PKT) and `upn-001` (0547110010 Gold, 23:07 PKT).

## In Progress (autonomous on edge)
- [ ] **149 posts firing automatically** at ~100-min intervals across May 10-21. Cron picks up the next due post on each `:07/:22/:37/:52` PKT tick. Per-post success email per fire.

## Pending
- [ ] **IG linkage** — Bilal's 3 sub-steps:
  1. Switch the new IG to a Business account (telecom category)
  2. Connect IG to the Golden Numbers UAE FB Page (via IG profile → Edit profile → Page)
  3. In Meta Business Suite, assign the IG asset to Sitara Infotech via the existing partnership (Settings → Partners → Sitara → Assign assets → Instagram → Full Control)
  Once done, re-call `/me/accounts?fields=id,name,access_token,instagram_business_account` to grab the new IG ID, drop into `/opt/meta-poster-upn/config.json` as `ig_user_id`. The same 149 queued JSONs (which already declare `["facebook","instagram"]` in platforms) will resume IG posting on the next cron tick — no other change needed thanks to the IG-null-skip patch.
- [ ] **TikTok** — new account `@telecom.store.uae`-style handle, clone `tiktok_poster.py` from GN, register pixel
- [ ] **YouTube** — new channel, run OAuth consent flow against the SHARED `goldennumbers-youtube` GCP project (do NOT create a new project — see memory `project-google-cloud-shared.md`). Cap UPN at 3 uploads/day to fit the 10k-unit shared quota.
- [ ] **Reels (video posts)** — when built, reuse the 6 pre-approved soundtracks at `/opt/meta-poster/music/` (`ambient-01/02`, `lofi-01`, `luxury-01/02`, `tension-01`). Don't curate new tracks — see memory `project-reels-music.md`.
- [ ] **Daily generator cron** — currently the 150-post queue is one-shot. After May 21 the queue is empty. Add `0 2,10,18 * * *` cron on edge mirroring GN's pattern (offset 30 min from GN's `30 1,9,17`). Until then, run `daily_generator.py --force` manually when the queue runs low.
- [ ] **Cross-share between GN ⇄ UPN** — Phase 5+ when both stable. ~25% of posts (NOT 100%) — see memory `project-cross-share-deferred.md`. Anti-spam threshold rules; both brands share AI Sync App reputation.
- [ ] **Per-Page daily ceiling guard** — code drafted, not deployed (Malik decided current load 30/45 daily is safe). Reactivate if scaling past 20 posts/day per Page. See memory `project-shared-app-limits.md`.

## Key Decisions
- **Same Meta App "AI Sync" for both brands** (vs creating a new app for UPN) — saves 2-7 days of App Review for advanced permissions. Trade-off: shared App reputation, both brands go down together if Meta flags one. Documented in `project-shared-app-limits.md`.
- **Same GCP project for both brands' YouTube** (when wired) — same logic; uplift quota or cap at 3/day each.
- **Number-led card design with plan tag** (vs plan-led) — Malik picked this in design discussion. Number is hero (Georgia Bold ~124pt dark on white), AED 188/MO red rounded tag in right column.
- **5 single + 10 grid posts/day** (inverted from GN's 10 + 5) — UPN tilts toward grid showcase to differentiate visually.
- **100-min slot interval** (vs GN's 96 min) + **first slot 20:30 PKT** + **30-min collision avoidance vs GN slots** — per Malik 2026-05-10. The avoidance code shifted first slot from 20:30 → 21:18 (GN had a 20:48 slot).
- **Author rule**: ALL commits authored by Malik Amin <amin@sitaratech.info>, no Co-Authored-By Claude trailers, no "Generated with Claude" footers in commits/PRs. See memory `feedback-commit-attribution.md`.
- **Email policy**: emails ONLY when post goes live or actual failure. No plan/queue/batch summaries. See memory `feedback-email-policy.md`.

## Files Modified (key paths)
- `runtime/meta_poster.py` — env-driven paths, fcntl Windows-safe, IG-null skip, YT marker auto-detect, BOM-tolerant config
- `runtime/notify.py` — UPN-branded From header, `[uaepremiumnumbers]` subject default
- `runtime/make_card.py` — red/white plan-tag single card (300 lines)
- `runtime/make_grid_card.py` — red/white grid card with 3 brand variants (400 lines)
- `runtime/score_numbers.py` — verbatim copy from GN, no adaptation needed
- `runtime/daily_generator.py` — UPN counts, plan-led captions, GN dedupe, 100-min interval, collision avoidance, email policy, fresh-deploy state defaults
- `runtime/config.json` — gitignored, contains FB Page Token (mirror of edge `/opt/meta-poster-upn/config.json`)
- `social-config/config.json` — initial config from token-generation step (legacy, kept)
- `.gitignore` — runtime artefacts + secrets
- `index.html`, `404.html`, `abu-dhabi/`, `dubai/`, `sharjah/`, `choose-number/`, `llms.txt` — FB URL swap
- All 150 cards under `cards/2026-05/` (singles + `cards/2026-05/grids/` for grid cards) — auto-generated by daily_generator, served by GitHub Pages
- `.fb-page-token.txt` — gitignored, raw token

## Uncommitted Changes
**All committed.** Last commit `36b22a8` on `main`, pushed to origin.

## Errors & Resolutions (this session)
- **GN deploy key only scoped to etisalat-shop** → Malik added `id_ed25519.pub` to uae-premium-numbers as deploy key (Read/write).
- **SSH config force-uses `github_deploy` key (registered on etisalat-shop only)** → Set `core.sshCommand` on `/opt/meta-poster-upn/site_repo/` to use `id_ed25519` explicitly with `IdentitiesOnly=yes`.
- **First daily_generator run hit batch-completion path on initial state** (`batch_day=1, size=1` defaults assume seed batch already exists) → Changed defaults to `batch_day=0, size=10, next_post_id=1` for UPN's fresh deploy.
- **PowerShell `Out-File -Encoding utf8` writes UTF-8 with BOM** → `load()` switched to `encoding='utf-8-sig'` for tolerance.
- **`push_cards` crashed with "nothing to commit" on re-runs after a push failure** → Added `git diff --cached --quiet` check; skip commit + push if no staged diff.
- **Slots collided with goldennummbers' scheduled_at** → Added `_avoid_gn_collisions(min_gap_min=30)` with cascading push.
- **upn-009 crashed on null `ig_user_id`** → Hotfix `e5168d4`: `if not cfg.get('ig_user_id'): skip` in IG branch + same null-aware condition in `ig_done`. Recovery: archived post manually, cleared breaker.
- **YT marker confused recipient** ("YT ⏳ queued" but no YT cron) → Hotfix `36b22a8`: `HAS_YOUTUBE = os.path.exists(BASE_DIR + '/youtube_config.json')` gates the marker. Auto-enables when YT comes online.

## Critical Context
- **Edge cron is LIVE** — `7-59/15 * * * *` is firing every 15 min. Posting will continue autonomously. If anything breaks, breaker email lands at `amin@sitaratech.info`.
- **Token expiry**: UPN FB Page token issued 2026-05-10. Rotate before 2026-07-09 (~60 days). Pattern is in `goldennummbers/docs/TOKEN_ROTATION_RUNBOOK.md` Rotation 2 — clone `goldennummbers/tools/rotate_fb_token.py` to UPN with the right config path.
- **GN site_repo on edge auth fix only applied to UPN's site_repo** — GN's existing setup at `/opt/meta-poster/site_repo/` is untouched and continues using its own `github_deploy` key against `etisalat-shop`. Don't touch GN's site_repo SSH config.
- **All 150 cards already on GitHub Pages** — even if cron fails, the image URLs are stable. FB has them cached after first hit.
- **`AI Sync` Meta App handles both brands** — if Meta flags either Page for spam, both pipelines can stop. Watch the per-Page daily volume; cap is 20/day per Page (5-buffer below Meta's 25 anti-spam threshold).
- **Memory location**: `C:\Users\Malik\.claude\projects\C--ST-Sitara-Infotech-uae-premium-numbers\memory\` — 11 entries indexed in `MEMORY.md`.
- **Bilal's IG linkage is the next strategic unblock** — once done, instructions are in this file under Pending → IG linkage. Token already covers IG scopes; just need the IG ID wired.
