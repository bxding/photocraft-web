# PhotoCraft Docker

Latest stable PhotoCraft web release. Images published daily by GitHub Actions.

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

