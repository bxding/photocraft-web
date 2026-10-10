import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { loadWasmChunks } from './wasm-chunks.mjs';

const manifestURL = new URL('https://example.com/subpath/wasm-chunks/hash/manifest.json');
const bytes = Uint8Array.from([0, 97, 115, 109, 1, 0, 0, 0]);
const checksum = createHash('sha256').update(bytes).digest('hex');
const manifest = { version: 1, size: 8, chunks: [{ file: '0000.bin', size: 8, sha256: checksum }] };

test('loader checks responses, lengths and checksums', async t => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  const mock = (metadata, chunkResponse) => {
    globalThis.fetch = async url => {
      if (String(url) === String(manifestURL)) return Response.json(metadata);
      assert.equal(String(url), new URL('0000.bin', manifestURL).href);
      return chunkResponse();
    };
  };
  mock(manifest, () => new Response(bytes));
  assert.deepEqual(await loadWasmChunks(manifestURL), bytes);
  mock(manifest, () => new Response(null, { status: 404 }));
  await assert.rejects(loadWasmChunks(manifestURL), /HTTP 404/);
  mock(manifest, () => new Response(bytes.slice(1)));
  await assert.rejects(loadWasmChunks(manifestURL), /wrong size/);
  mock(manifest, () => new Response(new Uint8Array(8)));
  await assert.rejects(loadWasmChunks(manifestURL), /checksum mismatch/);
  mock({ ...manifest, size: 9 }, () => new Response(bytes));
  await assert.rejects(loadWasmChunks(manifestURL), /Incomplete/);
  mock({ ...manifest, version: 2 }, () => new Response(bytes));
  await assert.rejects(loadWasmChunks(manifestURL), /Invalid WASM chunk manifest/);
  globalThis.fetch = async () => new Response(null, { status: 503 });
  await assert.rejects(loadWasmChunks(manifestURL), /manifest: HTTP 503/);
});
