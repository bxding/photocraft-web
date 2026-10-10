#!/usr/bin/env python3
"""Cloudflare Pages build command: compile upstream main and emit .pages/public."""
from datetime import datetime, timezone
import hashlib
import io
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
from urllib.request import Request, urlopen

from prepare_pages import prepare_site

ROOT = Path(__file__).resolve().parent.parent


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def download(url):
    request = Request(url, headers={"User-Agent": "photocraft-web-docker"})
    with urlopen(request, timeout=120) as response:
        return response.read()


def install_tools(checkout, tools, env):
    cargo_bin = Path(env.get("CARGO_HOME", str(Path.home() / ".cargo"))) / "bin"
    env["PATH"] = str(cargo_bin) + os.pathsep + env.get("PATH", "")
    env["RUSTUP_TOOLCHAIN"] = "stable"
    if not shutil.which("rustup", path=env["PATH"]):
        installer = tools / "rustup.sh"
        installer.write_bytes(download("https://sh.rustup.rs"))
        run("sh", str(installer), "-y", "--profile", "minimal", "--default-toolchain",
            "stable", "--no-modify-path", env=env)
    run("rustup", "toolchain", "install", "stable", "--profile", "minimal",
        "--target", "wasm32-unknown-unknown", env=env)

    # Follow upstream's Trunk pin without compiling Trunk itself.
    recipe = (checkout / "Dockerfile").read_text()
    match = re.search(r"^ARG TRUNK_VERSION=(\d+\.\d+\.\d+)\s*$", recipe, re.MULTILINE)
    if not match:
        raise ValueError("Cannot find upstream's TRUNK_VERSION in Dockerfile")
    arch = {"x86_64": "x86_64", "aarch64": "aarch64"}.get(platform.machine())
    if platform.system() != "Linux" or not arch:
        raise ValueError("This build command requires Linux amd64/arm64 (the Pages builder)")
    asset = f"trunk-{arch}-unknown-linux-musl.tar.gz"
    url = f"https://github.com/trunk-rs/trunk/releases/download/v{match[1]}/{asset}"
    archive = download(url)
    checksum = download(url + ".sha256").decode().split()[0]
    if hashlib.sha256(archive).hexdigest() != checksum:
        raise ValueError("Trunk download checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        binary = package.extractfile("trunk")
        if binary is None:
            raise ValueError("Trunk archive has no executable")
        trunk = tools / "trunk"
        trunk.write_bytes(binary.read())
        trunk.chmod(0o755)
    run(str(trunk), "--version", env=env)
    return trunk


def copy_notices(checkout, site):
    for name in ("LICENSE-MIT", "LICENSE-APACHE", "NOTICE", "ATTRIBUTION.md"):
        shutil.copy2(checkout / name, site / name)
    licenses = site / "licenses"
    licenses.mkdir(exist_ok=True)
    for pattern in ("assets/fonts/OFL-*.txt", "assets/icons/LICENSE-*.txt",
                    "assets/dict/LICENSE-*.txt", "crates/ui-egui/src/i18n/LICENSE-translations.txt"):
        for path in checkout.glob(pattern):
            shutil.copy2(path, licenses / path.name)
    shutil.copy2(checkout / "packaging/web/_headers", site / "_headers")


def main():
    if platform.system() != "Linux":
        raise SystemExit("Use this script in the Linux Pages builder; for local Docker builds use deploy-pages.py.")
    work_root = ROOT / ".pages"
    work_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="build-", dir=work_root) as directory:
        work = Path(directory)
        checkout = work / "upstream"
        run("git", "clone", "--depth", "1", "--branch", "main", "--single-branch",
            "https://github.com/storytold/photocraft.git", str(checkout))
        sha = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        print(f"Building PhotoCraft main at {sha}", flush=True)
        env = os.environ.copy()
        # Thin LTO and two jobs reduce memory pressure in the hosted builder.
        env.setdefault("CARGO_PROFILE_WASM_RELEASE_LTO", "thin")
        env.setdefault("CARGO_BUILD_JOBS", "2")
        env["PHOTOCRAFT_BUILD_SHA"] = sha
        env["PHOTOCRAFT_BUILD_DATE"] = f"{datetime.now(timezone.utc):%Y-%m-%d}"
        tools = work / "tools"
        tools.mkdir()
        trunk = install_tools(checkout, tools, env)
        # Build directly so upstream's release ZIP size gate doesn't reject a
        # large WASM before our chunking step can handle it.
        run(str(trunk), "build", "--release", "--locked",
            cwd=checkout / "apps/photocraft-web", env=env)
        site = checkout / "dist/web"
        copy_notices(checkout, site)
        prepared = prepare_site(site, work / "prepared")
        output = work_root / "public"
        if output.exists():
            shutil.rmtree(output)  # Only this script's generated output.
        shutil.move(str(prepared), str(output))
        print(f"Ready for Pages: {output}", flush=True)


if __name__ == "__main__":
    main()
