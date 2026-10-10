"""Download a published stable web release; never compile PhotoCraft."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen
import zipfile


def fetch(url):
    request = Request(url, headers={"User-Agent": "photocraft-web-docker"})
    with urlopen(request, timeout=120) as response:
        return response.read()


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "latest"
    endpoint = "latest" if version == "latest" else "tags/" + quote(version, safe="")
    release = json.loads(fetch("https://api.github.com/repos/storytold/photocraft/releases/" + endpoint))
    if release["draft"] or release["prerelease"]:
        raise ValueError("Only stable published releases are supported")
    tag = release["tag_name"]
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", tag):
        raise ValueError(f"Unexpected release tag: {tag}")
    assets = [a for a in release["assets"] if re.fullmatch(r"photocraft-web-[^/]+\.zip", a["name"])]
    if len(assets) != 1:
        raise ValueError("Expected exactly one released web ZIP")
    if len(sys.argv) < 3:
        print(tag)
        return
    asset = assets[0]
    data = fetch(asset["browser_download_url"])
    digest = asset.get("digest")
    if digest and digest != "sha256:" + hashlib.sha256(data).hexdigest():
        raise ValueError("Release ZIP checksum mismatch")
    destination = Path(sys.argv[2])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        roots = {PurePosixPath(e.filename).parts[0] for e in entries}
        if len(roots) != 1:
            raise ValueError("Expected one top-level directory in release ZIP")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Unsafe path in release ZIP")
            relative = Path(*path.parts[1:])
            if entry.is_dir():
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
    if not (destination / "index.html").is_file() or not list(destination.glob("*.wasm")):
        raise ValueError("Release is missing index.html or WebAssembly assets")
    (destination / "release.json").write_text(json.dumps({"version": tag, "url": release["html_url"]}) + "\n")
    print(f"Packaged {tag} from {asset['name']}")


if __name__ == "__main__":
    main()
