import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

from test_pages import make_site, wasm_module


class NativeBuildTests(unittest.TestCase):
    def test_native_build_exports_static_site_and_preserves_notices(self):
        module = runpy.run_path(str(Path(__file__).with_name("build-pages.py")))
        main = module["main"]
        calls = []

        def run(*args, **kwargs):
            calls.append((args, kwargs))
            if args[:2] == ("git", "clone"):
                checkout = Path(args[-1])
                checkout.mkdir()
                (checkout / "apps/photocraft-web").mkdir(parents=True)
                (checkout / "packaging/web").mkdir(parents=True)
                (checkout / "packaging/web/_headers").write_text("/*.wasm\n  Content-Type: application/wasm\n")
                for name in ("LICENSE-MIT", "LICENSE-APACHE", "NOTICE", "ATTRIBUTION.md"):
                    (checkout / name).write_text(name)
            elif args[1:] == ("build", "--release", "--locked"):
                checkout = kwargs["cwd"].parents[1]
                (checkout / "dist").mkdir()
                make_site(checkout / "dist/web", wasm_module())
            else:
                self.fail(f"Unexpected build command: {args}")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_output = root / ".pages/public"
            old_output.mkdir(parents=True)
            (old_output / "stale.txt").write_text("old build")
            with patch.dict(main.__globals__, {
                "ROOT": root, "run": run,
                "install_tools": lambda tools, env: tools / "trunk",
            }), patch("platform.system", return_value="Linux"), \
                    patch("subprocess.check_output", return_value="abc123\n"):
                main()
            self.assertTrue((old_output / "index.html").is_file())
            self.assertTrue((old_output / "LICENSE-MIT").is_file())
            self.assertFalse((old_output / "stale.txt").exists())
            self.assertIn("main", calls[0][0])
            build_env = calls[1][1]["env"]
            self.assertEqual(build_env["PHOTOCRAFT_BUILD_SHA"], "abc123")
            self.assertEqual(build_env["CARGO_BUILD_JOBS"], os.environ.get("CARGO_BUILD_JOBS", "2"))
            self.assertEqual((old_output / "robots.txt").read_text(), "User-agent: *\nDisallow: /\n")


if __name__ == "__main__":
    unittest.main()
