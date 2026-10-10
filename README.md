# PhotoCraft Docker

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

