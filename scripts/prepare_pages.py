"""Convert Trunk's web output into static Pages assets, each <= 19 MB."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil

MAX_ASSET_BYTES = 19_000_000  # Decimal MB: safely below both 20 MB and Pages' 25 MiB.


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.attributes = {}

    def handle_starttag(self, tag, attrs):
        if tag == "link":
            self.attributes = dict(attrs)


def prepare_site(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError(f"Output must be a new directory: {destination}")
    if source == destination or source in destination.parents:
        raise ValueError("Output cannot be inside the input directory")
    if not (source / "index.html").is_file():
        raise ValueError("Input has no index.html")
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Unexpected symlink: {path}")
        if path.name in {"_worker.js", "functions", "wrangler.toml", "wrangler.json", "wrangler.jsonc"}:
            raise ValueError(f"Static Pages only; refusing {path.name}")

    shutil.copytree(source, destination)
    shutil.copy2(Path(__file__).resolve().parent.parent / "robots.txt", destination / "robots.txt")
    index = destination / "index.html"
    html = index.read_text()
    wasm_files = sorted(destination.rglob("*.wasm"))
    if not wasm_files:
        raise ValueError("Input has no WASM files")
    loader = Path(__file__).with_name("wasm-chunks.mjs").read_bytes()
    loader_name = f"wasm-chunks-{hashlib.sha256(loader).hexdigest()[:16]}.mjs"
    for wasm in wasm_files:
        data = wasm.read_bytes()
        if data[:8] != b"\x00asm\x01\x00\x00\x00":
            raise ValueError(f"Invalid WASM header: {wasm.name}")
        if len(data) <= MAX_ASSET_BYTES:
            continue
        relative = wasm.relative_to(destination).as_posix()
        digest = hashlib.sha256(data).hexdigest()
        chunk_dir = destination / "wasm-chunks" / digest
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunks = []
        for number, start in enumerate(range(0, len(data), MAX_ASSET_BYTES)):
            chunk = data[start:start + MAX_ASSET_BYTES]
            name = f"{number:04d}.bin"
            (chunk_dir / name).write_bytes(chunk)
            chunks.append({"file": name, "size": len(chunk), "sha256": hashlib.sha256(chunk).hexdigest()})
        manifest = {"version": 1, "size": len(data), "chunks": chunks}
        (chunk_dir / "manifest.json").write_text(json.dumps(manifest) + "\n")
        manifest_path = f"./wasm-chunks/{digest}/manifest.json"
        # Trunk passes the hashed WASM URL explicitly to wasm-bindgen's init.
        # Keep the generated JS and all its bindings/SRI hashes untouched.
        pattern = r"module_or_path\s*:\s*(['\"])(?:\./)?" + re.escape(relative) + r"\1"
        replacement = (
            f"module_or_path: await (await import('./{loader_name}')).loadWasmChunks("
            f"new URL('{manifest_path}', document.baseURI))"
        )
        html, count = re.subn(pattern, lambda match: replacement, html)
        if count != 1:
            raise ValueError(f"Expected one Trunk init for {relative}; found {count}. Upstream loader changed.")

        def remove_preload(match):
            parser = LinkParser()
            parser.feed(match.group())
            attrs = parser.attributes
            if attrs.get("rel") == "preload" and attrs.get("href") in {relative, "./" + relative}:
                return ""
            return match.group()

        html = re.sub(r"<link\b[^>]*>", remove_preload, html, flags=re.IGNORECASE)
        (destination / loader_name).write_bytes(loader)
        wasm.unlink()
        print(f"Split {relative}: {len(data):,} bytes into {len(chunks)} chunks")

    index.write_text(html)
    # Stale precompressed copies would contain the old loader or oversized WASM.
    # Pages handles HTTP compression; upload only the uncompressed static assets.
    for path in destination.rglob("*"):
        if path.is_file() and path.suffix in {".gz", ".br"}:
            path.unlink()
    # Prevent Pages' implicit SPA fallback from returning HTML for missing chunks.
    if not (destination / "404.html").exists():
        (destination / "404.html").write_text("<!doctype html><title>Not found</title>Not found\n")
    with (destination / "_headers").open("a") as headers:
        headers.write("\n/\n  Cache-Control: no-cache\n/index.html\n  Cache-Control: no-cache\n")
        headers.write("/wasm-chunks/*\n  Cache-Control: public, max-age=31536000, immutable\n")
        headers.write("/wasm-chunks-*.mjs\n  Content-Type: text/javascript\n")
    files = [p for p in destination.rglob("*") if p.is_file()]
    oversized = [str(p.relative_to(destination)) for p in files if p.stat().st_size > MAX_ASSET_BYTES]
    if oversized:
        raise ValueError(f"Assets still exceed 19 MB: {', '.join(oversized)}")
    if len(files) > 20_000:
        raise ValueError("Site exceeds the Pages free-plan file count")
    print(f"Validated {len(files)} static assets; largest: {max(p.stat().st_size for p in files):,} bytes")
    return destination
