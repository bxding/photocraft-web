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

Large WASM files are split into 19 MB chunks and reassembled in the browser. Static Pages only—no Workers or Functions. `robots.txt` disallows all crawling.

Pages has a [20-minute build timeout](https://developers.cloudflare.com/pages/platform/limits/); a cold Rust build may exceed it.
