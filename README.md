# wowaudit wishlist updater

This keeps WoWAudit wishlists up to date for healers, without anyone at the keyboard:

```
wishlist.toml character
  → SimC profile        (Raider.io API by default, Blizzard API, or a pasted /simc export)
  → QE Live Upgrade Finder report   (headless Chromium via Playwright)
  → WoWAudit wishlist   (POST https://wowaudit.com/v1/wishlists)
```

QE Live's Upgrade Finder only supports healer specs, so the pipeline skips everyone else.

## Setup

### 1. Credentials (GitHub → Settings → Secrets and variables → Actions)

| Secret | Required? | Where to get it |
|---|---|---|
| `WOWAUDIT_SESSION` | One of these two. Without either, the run only generates reports and lists their links in the run summary. | Your own WoWAudit login. Run `uv run wishlist-updater --wowaudit-login`, then `gh secret set WOWAUDIT_SESSION < ~/.config/wishlist-updater/wowaudit-session.json`. The login lasts about a year, and once it expires the run fails with a "log in again" message. |
| `WOWAUDIT_API_KEY` | The alternative to the session | WoWAudit team settings → API (team admins only). If both are set, the API key wins. |
| `RAIDERIO_API_KEY` | No, it only raises the rate limit | https://raider.io/settings/apps |
| `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET` | Only with `simc_source = "blizzard"` | https://develop.battle.net/access/clients → Create Client |

### 2. Characters

Characters go in `wishlist.toml`. Its `[qe]` table holds the Upgrade Finder settings that every
run applies, and `simc_source` picks where the gear comes from:

- `raiderio` (default) is the public Raider.io API and needs no credentials. Its data is only as
  fresh as Raider.io's last crawl of the character, which for active players is usually within a day.
- `blizzard` is the Blizzard Profile API, which updates when the character logs out. It needs the
  two Blizzard secrets.

### 3. Runner

The workflow (`.github/workflows/update-wishlists.yml`) runs every day at 06:00 UTC, and you can
also start it by hand from the Actions tab. A manual run can take a raw `/simc` export instead of
using the Blizzard API, and that export includes your bags and currencies.

The job runs inside the `mcr.microsoft.com/playwright/python` container, so any runner with
Docker works:

- GitHub-hosted (`ubuntu-latest`) is the default and needs no setup.
- For the homelab, register a self-hosted runner on a Linux machine or VM with Docker
  (repo → Settings → Actions → Runners → New self-hosted runner), then set the repository
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

- Raider.io and the Blizzard API only expose the gear you have equipped. The rest of what the
  in-game addon exports, such as bag items, catalyst charges and upgrade currencies, is missing
  unless you pass a `/simc` export.
- Neither API exposes `redirected_base_stats` (catalysed tier pieces) or `crafted_stats` (crafted
  items), and without them QE's upgrade values are off by up to about 50%. That's why
  `wishlist.toml` stores them per slot in `item_overrides`. An override only applies while that
  slot still holds the same item, and the run summary warns you after you catalyse a tier piece
  or equip a new crafted item.

  To refresh the overrides, paste an in-game `/simc` export into the workflow's manual-run form
  (Actions → Update WoWAudit wishlists → Run workflow → `simc`). That run uses your full export
  and saves the new overrides to `wishlist.toml`. Locally, run
  `uv run wishlist-updater --refresh-overrides export.txt`. This only accepts in-game addon
  exports, because Raider.io and Warcraft Logs exports lack these fields.
- The QE Live automation drives the website's UI, so a QE redesign can break it. When a run
  fails, the workflow uploads screenshots as an artifact.
