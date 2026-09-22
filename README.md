# wowaudit wishlist updater

This keeps WoWAudit wishlists up to date for healers, without anyone at the keyboard:

```
wishlist.toml character
  → SimC profile        (Raider.io API by default, Blizzard API, or a pasted /simc export)
  → QE Live Upgrade Finder report   (headless Chromium via Playwright)
  → WoWAudit wishlist   (your own login session, or the team API key)
  → dashboard           (GitHub Pages)
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

The `[qe]` settings mirror the guild's droptimizer rules. `auto_gem = false` means no sockets get
added, and `upgrade_all_to_max = true` counts your equipped gear at its max upgrade level (the
closest thing QE has to Raidbots' "Match Droptimizer Item Levels").

`raid_difficulty` can be a single difficulty or a list. QE only runs one difficulty per report,
so every difficulty in the list becomes its own report and its own WoWAudit upload, in the
listed order. Keep `"Mythic"` last. Where two reports overlap (the +10 dungeon items), the last
upload wins, and the Mythic numbers are the ones the guild wants. The current setting is
`["Heroic", "Mythic"]`.

### 3. Runner

The workflow (`.github/workflows/update-wishlists.yml`) runs every day at 06:00 UTC, and you can
also start it by hand from the Actions tab. A manual run can take a raw `/simc` export instead of
using Raider.io, and that export includes your bags and currencies.

The job runs inside the `mcr.microsoft.com/playwright/python` container, so any runner with
Docker works:

- GitHub-hosted (`ubuntu-latest`) is the default and needs no setup.
- For the homelab, register a self-hosted runner on a Linux machine or VM with Docker
  (repo → Settings → Actions → Runners → New self-hosted runner), then set the repository
  variable `RUNS_ON` to `["self-hosted","linux"]`.

This repository is **public** (for the free dashboard), so it stays on GitHub-hosted runners.
Don't point `RUNS_ON` at a self-hosted homelab runner while it's public, and keep the workflow
limited to `schedule` and `workflow_dispatch`. A `pull_request` trigger on a self-hosted runner
would let anyone's fork run code on your homelab. The publish and save-overrides jobs always run
on `ubuntu-latest`.

## Local usage

```bash
uv sync
uv run playwright install chromium
# WoWAudit: your saved login (or WOWAUDIT_API_KEY). Raider.io needs nothing.
export WOWAUDIT_SESSION_FILE=~/.config/wishlist-updater/wowaudit-session.json

uv run wishlist-updater --dry-run --headed               # watch it, skip WoWAudit
uv run wishlist-updater --character Shiftheal --simc-file my.simc
uv run pytest                                            # offline tests
uv run pytest -m live                                    # hits real sites
```

## Dashboard

Every workflow run is published to https://bmiest.github.io/bmiest_wowaudit_wishlist_updater/,
including failed and report-only runs. It shows the run history, the Heroic and Mythic reports
with their top upgrades, and the gear you had equipped. The history lives on the
`dashboard-data` branch, which keeps the newest 200 runs. The pipeline only records data
there; `deploy-site.yml` is the one workflow that deploys the site. It runs after every pipeline
run, whenever `site/` changes on `main` (no pipeline run, no WoWAudit upload), and on demand,
and it always builds the latest `main` with the latest data.

The site is public, so it only gets data that is public anyway: gear, QE report results and run
status. Your WoWAudit session, your wishlist and the raw `/simc` export never go there.

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

## License

MIT, see [LICENSE](LICENSE). The peon in `site/assets/peon-jobs-done.*` is Blizzard
Entertainment's Warcraft III artwork, used on a non-commercial fan page. The MIT license
doesn't cover it.
