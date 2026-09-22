# wowaudit wishlist updater

Unattended pipeline that keeps WoWAudit wishlists current for healers:

```
wishlist.toml character
  → SimC profile        (Raider.io API by default, Blizzard API, or a pasted /simc export)
  → QE Live Upgrade Finder report   (headless Chromium via Playwright)
  → WoWAudit wishlist   (POST https://wowaudit.com/v1/wishlists)
```

QE Live's Upgrade Finder only supports healer specs, so non-healers are skipped.

## Setup

### 1. Credentials (GitHub → Settings → Secrets and variables → Actions)

| Secret | Required? | Where to get it |
|---|---|---|
| `WOWAUDIT_API_KEY` | no; without it the run only generates reports and lists their links in the run summary | WoWAudit team settings → API (team admin only) |
| `RAIDERIO_API_KEY` | no, only raises the rate limit | https://raider.io/settings/apps |
| `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET` | only with `simc_source = "blizzard"` | https://develop.battle.net/access/clients → Create Client |

### 2. Characters

Edit `wishlist.toml`. The `[qe]` table holds the Upgrade Finder settings applied on every run.
`simc_source` picks where the gear comes from:

- `raiderio` (default): public Raider.io API, no credentials. The data is only as fresh as
  Raider.io's last crawl of the character, which is usually within a day for active players.
- `blizzard`: Blizzard Profile API, updated when the character logs out. It needs the two
  Blizzard secrets.

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
export WOWAUDIT_API_KEY=...        # Raider.io needs nothing

uv run wishlist-updater --dry-run --headed               # watch it, skip WoWAudit
uv run wishlist-updater --character Shiftheal --simc-file my.simc
uv run pytest                                            # offline tests
uv run pytest -m live                                    # hits real sites
```

## Limitations

- Raider.io and the Blizzard API only expose **equipped** gear. Bag items, catalyst charges
  and upgrade currencies from the in-game addon are missing unless you pass a `/simc` export.
- Neither API exposes `redirected_base_stats` (catalysed tier pieces) or `crafted_stats` (crafted
  items), and without them QE's upgrade values are off by up to about 50%. `wishlist.toml`
  therefore stores them per slot in `item_overrides`, which you extract from a `/simc` export with
  `uv run wishlist-updater --extract-overrides export.txt`. An override applies only while
  that slot still holds the same item. After you swap a tier or crafted item, the run summary
  warns you to refresh the overrides.
- QE Live automation drives the website UI, so a QE redesign can break it. When a run fails,
  it uploads screenshots as a workflow artifact.
