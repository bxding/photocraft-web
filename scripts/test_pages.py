"""Run with: python3 -m unittest discover -s scripts -p 'test_*.py'"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from prepare_pages import MAX_ASSET_BYTES, prepare_site


def leb128(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result + bytes([value]))


def wasm_module(padding=0):
    # A real module exporting answer() -> 42, followed by a padded custom section.
    module = bytes.fromhex("0061736d010000000105016000017f03020100070a0106616e7377657200000a06010400412a0b")
    if padding:
        module += b"\0" + leb128(padding + 1) + b"\0" + bytes(padding)
    return module


def make_site(root, wasm):
    root.mkdir()
    (root / "app_bg.wasm").write_bytes(wasm)
    (root / "app.js").write_text(
        "export default async function init({module_or_path}) { "
        "return (await WebAssembly.instantiate(module_or_path)).instance.exports; }"
    )
    (root / "index.html").write_text('''<!doctype html><head>
<link rel="preload" href="./app_bg.wasm" as="fetch" integrity="original-wasm-hash">
<link rel="modulepreload" href="./app.js" integrity="original-js-hash">
<script type="module">
import init from './app.js';
const wasm = await init({ module_or_path: './app_bg.wasm' });
globalThis.answer = wasm.answer();
</script></head>''')


class PagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.output = self.root / "public"

    def test_large_wasm_runs_after_chunking(self):
        original = wasm_module(27_000_000)  # Exceeds Cloudflare's actual 25 MiB cap.
        make_site(self.source, original)
        (self.source / "index.html.gz").write_bytes(b"stale")
        prepare_site(self.source, self.output)
        self.assertFalse((self.output / "app_bg.wasm").exists())
        self.assertFalse((self.output / "index.html.gz").exists())
        self.assertTrue((self.source / "app_bg.wasm").exists())
        html = (self.output / "index.html").read_text()
        self.assertNotIn('rel="preload"', html)
        self.assertIn('integrity="original-js-hash"', html)
        self.assertEqual((self.source / "app.js").read_bytes(), (self.output / "app.js").read_bytes())
        manifests = list(self.output.rglob("manifest.json"))
        self.assertEqual(len(manifests), 1)
        manifest = json.loads(manifests[0].read_text())
        reconstructed = b"".join((manifests[0].parent / c["file"]).read_bytes() for c in manifest["chunks"])
        self.assertEqual(hashlib.sha256(original).digest(), hashlib.sha256(reconstructed).digest())
        self.assertTrue(all(p.stat().st_size <= MAX_ASSET_BYTES for p in self.output.rglob("*") if p.is_file()))
        # Execute the patched Trunk bootstrap, not just the helper in isolation.
        bootstrap = html.split('<script type="module">')[1].split('</script>')[0]
        setup = '''
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
globalThis.document = { baseURI: new URL('./', import.meta.url).href };
globalThis.fetch = async url => new Response(await readFile(url));
'''
        runner = self.output / "test-bootstrap.mjs"
        runner.write_text(setup + bootstrap + '\nassert.equal(globalThis.answer, 42);\n')
        # Node treats generated .js bindings as ES modules, like script type=module.
        (self.output / "package.json").write_text('{"type":"module"}')
        subprocess.run(["node", str(runner)], check=True)

    def test_small_wasm_and_bootstrap_unchanged(self):
        make_site(self.source, wasm_module())
        (self.source / "robots.txt").write_text("User-agent: *\nAllow: /\n")
        prepare_site(self.source, self.output)
        self.assertEqual((self.output / "robots.txt").read_text(), "User-agent: *\nDisallow: /\n")
        self.assertEqual((self.source / "index.html").read_text(), (self.output / "index.html").read_text())
        self.assertEqual((self.output / "app_bg.wasm").read_bytes(), wasm_module())

    def test_rejects_other_oversized_files(self):
        make_site(self.source, wasm_module())
        with (self.source / "huge.dat").open("wb") as f:
            f.truncate(MAX_ASSET_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "still exceed"):
            prepare_site(self.source, self.output)

    def test_rejects_changed_upstream_bootstrap(self):
        make_site(self.source, wasm_module(MAX_ASSET_BYTES))
        (self.source / "index.html").write_text('<script>differentLoader()</script>')
        with self.assertRaisesRegex(ValueError, "Upstream loader changed"):
            prepare_site(self.source, self.output)

    def test_rejects_workers_and_functions(self):
        make_site(self.source, wasm_module())
        for name in ["_worker.js", "functions", "wrangler.toml"]:
            with self.subTest(name=name):
                forbidden = self.source / name
                forbidden.write_text("not static")
                with self.assertRaisesRegex(ValueError, "Static Pages only"):
                    prepare_site(self.source, self.output)
                forbidden.unlink()

    def test_rejects_symlinks(self):
        make_site(self.source, wasm_module())
        (self.source / "link").symlink_to(self.source / "app_bg.wasm")
        with self.assertRaisesRegex(ValueError, "symlink"):
            prepare_site(self.source, self.output)

    def test_rejects_overwriting_existing_output(self):
        make_site(self.source, wasm_module())
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, "new directory"):
            prepare_site(self.source, self.output)


if __name__ == "__main__":
    unittest.main()
