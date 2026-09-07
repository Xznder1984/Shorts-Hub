# Shorts Hub

A minimalist, TikTok-style vertical video feed that aggregates **YouTube Shorts**, **TikTok**, and
**Instagram Reels** into a single unified search + browse experience. Built to run lean on a
low-power home server (e.g. a Dell Latitude E7240 repurposed as Proxmox host) and reachable over
the internet via Caddy + HTTPS.

---

## Quick Start (Proxmox / any Debian VM or LXC)

The easiest way is the one-line installer. On your Proxmox LXC/VM (Debian/Ubuntu):

```bash
curl -fsSL https://raw.githubusercontent.com/Xznder1984/Shorts-Hub/main/deploy/install.sh | bash
```

The installer will:

1. Check for `git`, `docker`, and `docker compose` (and install missing ones via `apt` on request)
2. Clone the repo to `~/shorts-hub`
3. Create `.env` from `.env.example` (you add your YouTube API key)
4. Ask for your domain and patch the Caddyfile
5. Run `docker compose up -d --build`

> **Re-running the installer updates the app.**

If you'd rather do it manually, keep reading.

---

## Architecture

```
                    ┌──────────────────────────────────────┐
   Internet / LAN    │  Caddy (reverse proxy, auto-HTTPS)   │
   ─────────────────▶│  :80 / :443                          │
                    └──────────────┬───────────────────────┘
                                   │ /api/*          │ /*
                                   ▼                 ▼
                        ┌────────────────────┐  ┌────────────────────┐
                        │  backend (FastAPI)  │  │ frontend (static,  │
                        │  :8000              │  │ nginx, :80)        │
                        │                     │  │  SvelteKit build    │
                        │  sources/           │  └────────────────────┘
                        │   ├─ youtube.py     │
                        │   ├─ tiktok.py      │
                        │   └─ instagram.py   │
                        │  aggregator.py      │
                        │  cache (SQLite)     │
                        └────────────────────┘
```

## Directory layout

```
Shorts-Hub/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # FastAPI app + endpoints
│       ├── models.py          # unified VideoItem schema
│       ├── cache.py           # SQLite result cache
│       ├── aggregator.py      # merge/dedupe/interleave
│       └── sources/
│           ├── __init__.py    # BaseSource interface
│           ├── youtube.py     # official YouTube Data API v3
│           ├── tiktok.py      # scraping-based (fragile)
│           └── instagram.py   # scraping-based (fragile)
├── frontend/
│   ├── Dockerfile             # node build -> nginx serve
│   ├── nginx.conf
│   ├── svelte.config.js
│   └── src/
│       ├── routes/+page.svelte
│       ├── lib/components/
│       │   ├── Feed.svelte
│       │   ├── SearchBar.svelte
│       │   └── VideoPlayer.svelte
│       ├── lib/stores/feed.ts
│       └── service-worker.js  # PWA
├── deploy/
│   ├── Caddyfile
│   └── install.sh             # one-command installer
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Platform integrations

| Platform | Type | Status | Notes |
|----------|------|--------|-------|
| **YouTube Shorts** | Official API (`search.list`, `videos.list`) | ✅ **Stable / supported** | Requires `YOUTUBE_API_KEY`. Filtered to short-form (≤60s). Embeds natively. |
| **TikTok** | Web scraping (public internal API) | ⚠️ **Fragile** | No official public API for this. Isolated module; **best-effort**. May need updates when TikTok changes endpoints. |
| **Instagram Reels** | Web scraping (public web API) | ⚠️ **Fragile** | No official public API for generic Reels search. Isolated module; **best-effort**. |

### What to do when a scraper breaks

- The backend treats each source independently. If TikTok or Instagram throws an error, it's
  caught and that platform is simply skipped — the app keeps working with the remaining sources
  (typically YouTube-only).
- To disable a broken source permanently, remove its API key/credentials from `.env` (for TikTok/
  IG they now have no config toggles — see below) or edit `backend/app/main.py` to drop the module
  from the `Aggregator(...)` list and rebuild.
- The clean path is to add a config flag. To disable collecting from a source at runtime, set the
  corresponding key empty in `.env`:
  - TikTok: uses `TIKTOK_SESSION_COOKIE`. If you want a hard on/off, leave this blank.
  - Instagram: uses `INSTAGRAM_USERNAME` / `INSTAGRAM_PASSWORD`.

> Note: TikTok and Instagram modules currently default to *available* even with empty credentials
> (they work anonymous/best-effort). To hard-disable them, remove them from the source list in
> `backend/app/main.py`:
> ```python
> aggregator = Aggregator([youtube], cache)   # YouTube only
> ```

---

## Local development

### Backend (Python 3.11+)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Copy env template and add your YOUTUBE_API_KEY
cp ../.env.example ../.env        # then edit ../.env

uvicorn app.main:app --reload --port 8000
```

Test it:

```bash
curl "http://localhost:8000/api/health"
curl "http://localhost:8000/api/status"
curl "http://localhost:8000/api/search?q=dogs"
curl "http://localhost:8000/api/feed?limit=10"
```

### Frontend (Node 20+)

```bash
cd frontend
npm install

# In dev, point the frontend at your local backend:
# (create frontend/.env.local with the line below, or export it)
echo "VITE_API_URL=http://localhost:8000" > .env.local

npm run dev
# open http://localhost:5173
```

---

## Build & run with Docker (local or Proxmox)

```bash
# 1. Copy and edit .env (add YOUTUBE_API_KEY)
cp .env.example .env
nano .env

# 2. Set your domain in the Caddyfile (or use the HTTP-only internal setup)
nano deploy/Caddyfile

# 3. Build & start
docker compose up -d --build

# 4. Verify
docker compose ps
docker compose logs -f backend
```

The frontend is served on the host at port 80 (via Caddy). The API is at `/api/*` through Caddy.

---

## Proxmox deployment (manual, step by step)

These steps assume a **Debian/Ubuntu LXC or VM** on Proxmox with Docker installed.

### 0. VM or CT (LXC)? — recommendation

**Use an LXC container (CT).** This app is a trusted personal workload (your own code, no
untrusted images) and you're on a low-power host (E7240, 16 GB RAM). An unprivileged LXC shares
the host kernel, uses dynamic RAM with near-zero overhead, and boots in seconds. Docker Compose
works fine inside a modern Proxmox LXC once **nesting** and **keyctl** are enabled.

| | LXC (CT) ✅ recommended | KVM VM |
|---|---|---|
| RAM overhead | ~0 (shares host kernel, dynamic limits) | ~300 MB+ reserved for the guest OS |
| Boot time | seconds | slower (full OS boot) |
| Isolation | Good (unprivileged, UID-mapped root) | Best (own kernel, hardware boundary) |
| Docker support | Works with `nesting=1,keyctl=1`; fuse-overlayfs on Debian 12+ | Fully supported, no caveats |
| Proxmox official stance | Not officially supported (works great for homelab) | Fully supported, live-migration |
| Best for | **Density / efficiency / low-power hosts** ✅ | Untrusted workloads, production multi-tenant |

**If you'd rather not deal with Docker-in-LXC caveats at all, a small VM (2 vCPU / 2 GB RAM /
8 GB disk, Debian 12 cloud image) is the "supported" path** — same compose file works unchanged.

### 1. Create the LXC

From the Proxmox shell (or GUI: local template → Debian 13):

```bash
# Download the Debian template if you haven't
pveam update
pveam download local debian-13-standard_13.5-1_amd64.tar.zst

# Create an UNPRIVILEGED container with Docker's required features
pct create 110 local:vztmpl/debian-13-standard_13.5-1_amd64.tar.zst \
  --hostname shortshub \
  --cores 2 \
  --memory 2048 --swap 512 \
  --rootfs local-lvm:12 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=1,keyctl=1

pct start 110
pct enter 110
```

> GUI equivalent: **Create CT** → pick Debian 13 template → check **Nesting** and **keyctl**
> under Options → Features. Unprivileged is the default and correct choice.

Install Docker inside the container:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # log out & back in (or use sudo docker)
docker run --rm hello-world     # sanity check
```

### 2. Clone the repo (skip if you used the installer)

```bash
git clone https://github.com/Xznder1984/Shorts-Hub.git ~/shorts-hub
cd ~/shorts-hub
```

### 3. Configure secrets

```bash
cp .env.example .env
nano .env        # add your YOUTUBE_API_KEY
```

### 4. Start

```bash
docker compose up -d --build
docker compose ps
```

Persistent state (the SQLite cache DB) is stored in the `shortshub-data` Docker volume, so restarts
and `docker compose down/up` keep results cached.

### 5. Getting HTTPS with Caddy (public access)

1. **DNS**: create an `A` record for your subdomain (e.g. `shorts.example.com`) pointing at your
   **public IP**.
2. **Port forwarding**: on your router, forward **TCP 80** and **TCP 443** to the IP of this
   Proxmox LXC/VM.
3. **Edit the Caddyfile** and replace `shorts.example.com` with your real domain:
   ```bash
   nano deploy/Caddyfile
   ```
4. **Restart Caddy**:
   ```bash
   docker compose restart caddy
   docker compose logs -f caddy     # watch it obtain a cert
   ```

Caddy automatically obtains and **auto-renews** Let's Encrypt TLS certificates — nothing to manage.

### 6. Locking it down (recommended)

A personal app exposed to the internet should have at least a login gate. **This is a recommended
follow-up** — no auth is built in by default. Easiest options in `deploy/Caddyfile`:

**Basic auth (username/password):**
```caddyfile
shorts.example.com {
    basic_auth {
        # generate a hash with: docker run --rm caddy caddy hash-password
        myuser $2a$14$XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    }
    ...
}
```

**IP allowlist:**
```caddyfile
shorts.example.com {
    @blocked not remote_ip 192.168.0.0/16 10.0.0.0/8
    handle @blocked {
        respond "Forbidden" 403
    }
    ...
}
```

Both are documented inline in `deploy/Caddyfile`.

---

## Updating the app

```bash
cd ~/shorts-hub
git pull
docker compose up -d --build
```

Or re-run the one-line installer (it pulls and rebuilds).

---

## Configuration reference (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `YOUTUBE_API_KEY` | **Yes** | YouTube Data API v3 key (https://console.cloud.google.com/apis/credentials) |
| `TIKTOK_SESSION_COOKIE` | No | Optional TikTok session cookie (higher limits, best-effort) |
| `INSTAGRAM_USERNAME` | No | Optional Instagram login (some features/limits) |
| `INSTAGRAM_PASSWORD` | No | Optional Instagram password |
| `BACKEND_PORT` | No | Backend port (default `8000`) — used for local dev |
| `CACHE_TTL` | No | Cache TTL in seconds (default `10800` = 3h) |
| `RATE_LIMIT_PER_MINUTE` | No | Outbound requests/min per platform (default `20`) |

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness + available sources |
| GET | `/api/status` | Which sources are available/disabled |
| GET | `/api/search?q=&limit=&offset=` | Search all sources, merged + interleaved |
| GET | `/api/feed?limit=&offset=` | Auto-populated feed from cached/trending results |

### Unified video schema

```json
{
  "id": "yt_abc123",
  "source": "youtube",
  "video_url": "https://...",
  "thumbnail_url": "https://...",
  "caption": "...",
  "hashtags": ["shorts", "funny"],
  "author_name": "Channel",
  "author_handle": "@channel",
  "author_profile_url": "https://...",
  "channel_url": "https://...",
  "original_post_url": "https://...",
  "published_at": "2024-01-01T00:00:00Z",
  "duration_seconds": 45,
  "embed_url": "https://www.youtube.com/embed/abc123",
  "can_embed": true
}
```

---

## Notes on the tech stack

- **Backend**: FastAPI + `httpx` async, `aiosqlite` for caching, Pydantic for the unified schema.
- **Frontend**: SvelteKit (static adapter) — small JS bundle, ideal for low-power hardware. Served
  by nginx. PWA via `manifest.webmanifest` + service worker (offline fallback, installable to homescreen).
- **Reverse proxy**: Caddy for automatic HTTPS.
- **Resource usage**: everything is async and cached; the SQLite DB avoids re-hitting API/scraper
  quota on repeat searches. Designed to run comfortably within the E7240's 16 GB RAM (uses ~200–400 MB).

---

## License

Private/personal project. See your own usage terms for TikTok/Instagram/YouTube.
