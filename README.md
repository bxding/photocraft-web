# PhotoCraft Web

Bleeding-edge [PhotoCraft](https://github.com/storytold/photocraft) on Cloudflare Pages.

Connect this repo to a **Pages** project:

```text
Framework:         None
Build command:     python3 scripts/build-pages.py
Output directory:  .pages/public
Production branch: main
```

Each push here builds the latest upstream `main`. Upstream commits alone don't trigger a build.

## Rebuild every 6 hours

1. In this repo, open **Settings → Secrets and variables → Actions → New repository secret**.
2. Name: `CLOUDFLARE_PAGES_DEPLOY_HOOK`. Value: your Cloudflare Pages deploy hook URL for `main`.
3. Open **Actions → Trigger Pages rebuild → Run workflow** to test it.

The workflow requests builds at 00:17, 06:17, 12:17, and 18:17 UTC. GitHub may delay scheduled runs or disable them after 60 days without repo activity. Remove your server's old cron entry to avoid duplicate builds.

The instance notice stays dismissed in that browser after clicking ×, including reloads and reopening the site (until site storage is cleared).

Large WASM files are split into 19 MB chunks and reassembled in the browser. Static Pages only—no Workers or Functions. `robots.txt` disallows all crawling.

Pages has a [20-minute build timeout](https://developers.cloudflare.com/pages/platform/limits/); a cold Rust build may exceed it.
