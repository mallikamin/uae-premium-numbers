# uae-premium-numbers Error Log

Cumulative log of errors encountered and fixed during development. Any agent (Claude, Codex, Cursor, DeepSeek) working on this project should read this file first to avoid repeating known mistakes, and append new entries when fixing errors.

---

## Format

Each entry follows:
### [DATE] — Short title
- **Error**: Exact error message or symptom
- **Context**: What was being done when it happened
- **Root Cause**: Why it happened
- **Fix**: What was changed
- **Rule**: What to do differently going forward

---

### 2026-05-10 — GitHub deploy key permission denied on first push
- **Error**: `git push failed: ERROR: Permission to mallikamin/uae-premium-numbers.git denied to deploy key. fatal: Could not read from remote repository.`
- **Context**: First `daily_generator.py --force` run on edge tried to push 15 rendered cards to the new repo's `site_repo`. Run 1 (and subsequent odd-numbered runs) failed at git push.
- **Root Cause**: The edge SSH config at `~/.ssh/config` force-uses `github_deploy` (`IdentitiesOnly yes`), which is registered as a deploy key only on `mallikamin/etisalat-shop` — not on `mallikamin/uae-premium-numbers`. Malik separately added the loom-edge `id_ed25519.pub` to the new repo, but SSH never offered that key.
- **Fix**: Set per-repo `core.sshCommand` on edge: `git -C /opt/meta-poster-upn/site_repo config core.sshCommand 'ssh -i /home/loom-edge-01/.ssh/id_ed25519 -o IdentitiesOnly=yes'`
- **Rule**: When a new repo gets a deploy key on edge, also override `core.sshCommand` for that repo's clone — don't assume the global SSH config will route correctly. GN's site_repo keeps using `github_deploy`; UPN's site_repo uses `id_ed25519`.

### 2026-05-10 — push_cards crashes "nothing to commit" on re-run
- **Error**: `RuntimeError: git commit -m Daily card drop (15 cards) — 2026-05-10 failed:` (empty stderr)
- **Context**: After run 1's push failed, runs 2-10 re-rendered the same cards (state wasn't saved in run 1's crash). git add saw no diff against the (now-orphaned) failed commit, but `git commit` exited non-zero with "nothing to commit".
- **Root Cause**: `push_cards()` had no idempotent re-run guard. Whenever git add staged nothing new, the commit step crashed, taking down the whole run before JSON-writing + state-save.
- **Fix**: Added `git diff --cached --quiet` check before commit; if no staged diff, skip commit + push and continue to JSON writing.
- **Rule**: Any production poster pipeline must be idempotent on re-run. Crashes that strand state are worse than no-ops that resume cleanly.

### 2026-05-10 — meta_poster trips circuit breaker on null ig_user_id
- **Error**: `IG HTTP 400: {"error":{"message":"Unsupported post request. Object with ID 'None' does not exist..."}}` followed by `CIRCUIT BREAKER TRIPPED: Post upn-009 failed 2 times.`
- **Context**: First production cron firing (upn-009 at 21:22 PKT). FB posted successfully (`fb_post_id=969170162937075_122130585855164173`). IG step then POSTed to `graph.facebook.com/v21.0/None/media` because `cfg.ig_user_id` is `null` (Bilal's IG linkage pending).
- **Root Cause**: `daily_generator.py` writes `"platforms": ["facebook", "instagram"]` on every post by default. `meta_poster.py` saw "instagram" in platforms and called `post_instagram()` without checking that `ig_user_id` was actually configured. After 2 retry-failures, breaker tripped → all 149 queued posts halted.
- **Fix**: Two changes in `meta_poster.py`:
  1. IG branch now checks `if not cfg.get('ig_user_id')` and skips silently (logs "IG skip — ig_user_id not configured; FB-only").
  2. `ig_done` calculation extended: `('instagram' not in platforms) or post.get('posted_ig') or not cfg.get('ig_user_id')`.
  Recovery: manually stripped `retry_at` + `failed_attempts` from upn-009.json, moved to archive/, cleared `CIRCUIT_BREAKER.flag`.
- **Rule**: Any platform branch in any poster pipeline must check that the platform's user_id/account_id is actually present in config before making API calls. Unconfigured platform = no-op, not a failure. Same defensive pattern applies to TikTok, YouTube, Reels when those come online.

### 2026-05-10 — Misleading "YT ⏳ queued" line in UPN success emails
- **Error**: Per-post success email for UPN included `Out: FB ✅ + YT ⏳ queued (next :05 or :35 cron tick, 5/day cap)` even though UPN has no YouTube cron deployed.
- **Context**: First successful UPN post (upn-001) sent its success email at 23:07 PKT. The "YT queued" promise was untrue — `youtube_shorts_poster.py` has not been deployed for UPN.
- **Root Cause**: `_yt_status_marker(post)` in `meta_poster.py` was inherited verbatim from goldennummbers. It always returns "YT ⏳ queued" when `posted_youtube` isn't set, with no awareness of whether a YT pipeline actually exists for the brand.
- **Fix**: Added `HAS_YOUTUBE = os.path.exists(f'{BASE_DIR}/youtube_config.json')` at import-time. `_yt_status_marker` returns `''` when False. `email_post_success` skips appending when marker is empty.
- **Rule**: Per-platform UI text in shared poster code should auto-detect whether the platform is wired for the brand instead of unconditionally promising future activity. Use config-file existence checks (`youtube_config.json`, `tiktok_config.json`, etc.) rather than hardcoded brand awareness.

### 2026-05-10 — UTF-8 BOM trips Python json.load on Windows-written configs
- **Error**: `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
- **Context**: First smoke-test of `meta_poster.py` on Windows after PowerShell wrote `runtime/config.json` via `Out-File -Encoding utf8`.
- **Root Cause**: PowerShell 5.1's `Out-File -Encoding utf8` prepends a UTF-8 BOM (`\xef\xbb\xbf`). Python 3.x's `json.load(open(path))` doesn't strip the BOM and chokes on the leading non-JSON bytes.
- **Fix**: Switched `load(path)` in `meta_poster.py` to `open(path, encoding='utf-8-sig')` — the `-sig` codec strips the BOM transparently. Plain UTF-8 still parses fine.
- **Rule**: Any config file that may be touched by Windows PowerShell should be loaded with `utf-8-sig` encoding. This is also defense for scp-from-Windows-to-Linux scenarios. Better than mandating "use specific PowerShell flags" which is easy to forget.

### 2026-05-10 — daily_generator first-run instantly hits batch-completion path
- **Error**: First `python daily_generator.py --force` on a freshly-deployed edge printed `Batch 1 complete; pause flag set; awaiting review.` instead of generating posts.
- **Context**: Brand-new deploy, no `batch_state.json` yet, no posts in approved/. Expected: generate 15 posts. Actual: pause + halt.
- **Root Cause**: `load_state()` returned `{batch:1, batch_day:1, batch_size_days:1, next_post_id:16, ...}` as defaults. Condition `state["batch_day"] >= state["batch_size_days"]` (1 >= 1) immediately fired, treating the fresh deploy as "batch 1 already done its 1 day". Defaults were inherited from goldennummbers, where gn-001..gn-015 had been hand-seeded before daily_generator's first run.
- **Fix**: Changed UPN's `load_state()` defaults to `batch_day:0, batch_size_days:10, next_post_id:1`. UPN skips the 1-day pilot batch entirely and runs the 10-day cadence directly.
- **Rule**: When cloning a state-machine script from another brand, audit the defaults — they may encode that brand's seeding history. For fresh deploys, prefer explicit zero-state defaults over copy-paste.
