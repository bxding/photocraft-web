# PhotoCraft Web

PhotoCraft web release. Automatic image updates are currently disabled.

Save as `docker-compose.yaml`:

```yaml
services:
  photocraft:
    image: ghcr.io/bxding/photocraft-web-docker:latest
    ports:
      - "127.0.0.1:8080:8080"
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp:size=64m,mode=1777
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
```

Start or update:

```sh
docker compose up -d --pull always
```

Open **http://localhost:8080**, or point your host NGINX proxy to `http://127.0.0.1:8080`.

For a Docker-based proxy, use a shared network and `http://photocraft:8080`.

## Cloudflare Pages (bleeding-edge main)

Connect this GitHub repo to a **Pages** project:

- Framework preset: **None**
- Build command: `python3 scripts/build-pages.py`
- Build output directory: `.pages/public`
- Production branch: `main`

Each push here builds the latest PhotoCraft `main`. Upstream commits alone don't trigger a build.
WASM is split into 19 MB chunks. No Workers or Functions.
Pages has a [20-minute build timeout](https://developers.cloudflare.com/pages/platform/limits/); a cold Rust build may exceed it.
An existing Direct Upload project needs a new Git-connected Pages project for automatic builds.

### Manual deployment

Requires Docker running, Git, Python 3, and Node.js 22+.

```sh
npx wrangler@4 login
npx wrangler@4 pages project create photocraft --production-branch main
python3 scripts/deploy-pages.py photocraft
```

Skip project creation if it already exists. Run the last command again to update.
Builds upstream `main`, splits large WASM into 19 MB chunks, and reassembles them in the browser. Static Pages only—no Workers or Functions. The full WASM still downloads and uses browser memory.

To build without deploying: `python3 scripts/deploy-pages.py --prepare-only`.
To deploy an existing build: `python3 scripts/deploy-pages.py photocraft --site /path/to/dist/web`.

