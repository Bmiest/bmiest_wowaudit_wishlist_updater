# wowaudit wishlist updater

Unattended pipeline that keeps WoWAudit wishlists current for healers:

```
wishlist.toml character
  → SimC profile        (Blizzard Profile API, or a pasted /simc export)
  → QE Live Upgrade Finder report   (headless Chromium via Playwright)
  → WoWAudit wishlist   (POST https://wowaudit.com/v1/wishlists)
```

QE Live's Upgrade Finder only supports healer specs, so non-healers are skipped.

## Setup

### 1. Credentials (GitHub → Settings → Secrets and variables → Actions)

| Secret | Where to get it |
|---|---|
| `WOWAUDIT_API_KEY` | WoWAudit team settings → API (team admin only) |
| `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET` | https://develop.battle.net/access/clients → Create Client (free, no redirect URL needed) |

### 2. Characters

Edit `wishlist.toml`. The `[qe]` table holds the Upgrade Finder settings applied on every run.

### 3. Runner

The workflow (`.github/workflows/update-wishlists.yml`) runs daily at 06:00 UTC, and you can
start it manually from the Actions tab. For a manual run you can pass a raw `/simc` export,
which includes your bags and currencies, instead of using the Blizzard API.

The job runs inside the `mcr.microsoft.com/playwright/python` container, so any runner with
Docker works:

- **Default: GitHub-hosted** (`ubuntu-latest`). Nothing to set up.
- **Homelab:** register a self-hosted runner on a Linux machine or VM with Docker
  (repo → Settings → Actions → Runners → New self-hosted runner). Then set the repository
  variable `RUNS_ON` to `["self-hosted","linux"]`.

Keep this repository **private**, and keep the workflow limited to `schedule` and
`workflow_dispatch`. A `pull_request` trigger on a self-hosted runner would let untrusted
code run on your homelab.

## Local usage

```bash
uv sync
uv run playwright install chromium
export WOWAUDIT_API_KEY=... BLIZZARD_CLIENT_ID=... BLIZZARD_CLIENT_SECRET=...

uv run wishlist-updater --dry-run --headed               # watch it, skip WoWAudit
uv run wishlist-updater --character Shiftheal --simc-file my.simc
uv run pytest                                            # offline tests
uv run pytest -m live                                    # hits real sites
```

## Limitations

- The Blizzard API only exposes **equipped** gear. Bag items, catalyst charges and upgrade
  currencies from the in-game addon are missing unless you pass a `/simc` export.
- Stats of catalysed tier pieces (`redirected_base_stats`) aren't in the API, so QE uses the
  tier item's default secondary stats for those slots.
- QE Live automation drives the website UI, so a QE redesign can break it. When a run fails,
  it uploads screenshots as a workflow artifact.
