#!/usr/bin/env python3
"""Build PhotoCraft main, split large WASM assets, and deploy to static Pages."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import tempfile

from prepare_pages import prepare_site

ROOT = Path(__file__).resolve().parent.parent


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", help="Cloudflare Pages project name")
    parser.add_argument("--branch", default="main", help="Pages deployment branch (default: main)")
    parser.add_argument("--prepare-only", action="store_true", help="Build and split without uploading")
    parser.add_argument("--site", type=Path, help="Use an existing Trunk dist/web directory instead of building")
    args = parser.parse_args()
    if not args.prepare_only and not args.project:
        parser.error("supply a Pages project name, or use --prepare-only")
    required = ([] if args.site else ["git", "docker"]) + ([] if args.prepare_only else ["npx"])
    for tool in required:
        if not shutil.which(tool):
            parser.error(f"{tool} is required")
    if not args.site:
        run("docker", "info", stdout=subprocess.DEVNULL)

    work_root = ROOT / ".pages"
    work_root.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="deploy-", dir=work_root))
    sha = None
    if args.site:
        source = args.site.resolve()
    else:
        with tempfile.TemporaryDirectory(prefix="photocraft-main-") as directory:
            checkout = Path(directory) / "upstream"
            run("git", "clone", "--depth", "1", "--branch", "main", "--single-branch",
                "https://github.com/storytold/photocraft.git", str(checkout))
            sha = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
            print(f"Building upstream main at {sha}", flush=True)
            # Reuse upstream's toolchain, features, fonts and license packaging.
            # Export static files only; no container is deployed to Cloudflare.
            recipe = (checkout / "Dockerfile").read_text()
            recipe += "\nFROM scratch AS pages-export\nCOPY --from=runtime /usr/share/nginx/html/ /\n"
            dockerfile = Path(directory) / "Dockerfile.pages"
            dockerfile.write_text(recipe)
            source = work / "raw"
            run("docker", "buildx", "build", "--pull", "--file", str(dockerfile),
                "--target", "pages-export", "--output", f"type=local,dest={source}",
                "--build-arg", f"PHOTOCRAFT_BUILD_SHA={sha}",
                "--build-arg", f"PHOTOCRAFT_BUILD_DATE={datetime.now(timezone.utc):%Y-%m-%d}",
                str(checkout))
    output = prepare_site(source, work / "public")
    print(f"Pages assets: {output}", flush=True)
    if args.prepare_only:
        return

    # Isolate Wrangler from repository configs or any local functions/ directory.
    # Only `pages deploy` is used; never `wrangler deploy` (Workers).
    with tempfile.TemporaryDirectory(prefix="photocraft-pages-upload-") as upload_dir:
        command = ["npx", "--yes", "wrangler@4", "pages", "deploy", str(output),
                   "--project-name", args.project, "--branch", args.branch]
        if sha:
            command += ["--commit-hash", sha, "--commit-message", f"PhotoCraft main {sha}"]
        run(*command, cwd=upload_dir)


if __name__ == "__main__":
    main()
