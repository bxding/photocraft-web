// Browser-side loader. The chunks are ordinary static Pages assets.
export async function loadWasmChunks(manifestURL) {
  const response = await fetch(manifestURL);
  if (!response.ok) throw new Error(`WASM manifest: HTTP ${response.status}`);
  const manifest = await response.json();
  if (manifest.version !== 1 || !Number.isSafeInteger(manifest.size) || manifest.size < 8 ||
      !Array.isArray(manifest.chunks) || manifest.chunks.length === 0) {
    throw new Error("Invalid WASM chunk manifest");
  }

  const bytes = new Uint8Array(manifest.size);
  let offset = 0;
  // Fetch sequentially to avoid retaining all the chunk buffers at once.
  for (const chunk of manifest.chunks) {
    if (!Number.isSafeInteger(chunk.size) || chunk.size <= 0 ||
        chunk.size > 19_000_000 || offset + chunk.size > bytes.length ||
        !/^[0-9]+\.bin$/.test(chunk.file) || !/^[a-f0-9]{64}$/.test(chunk.sha256)) {
      throw new Error("Invalid WASM chunk metadata");
    }
    const url = new URL(chunk.file, manifestURL);
    const part = await fetch(url);
    if (!part.ok) throw new Error(`WASM chunk ${chunk.file}: HTTP ${part.status}`);
    const buffer = await part.arrayBuffer();
    if (buffer.byteLength !== chunk.size) throw new Error(`WASM chunk ${chunk.file}: wrong size`);
    const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", buffer));
    const hex = Array.from(hash, byte => byte.toString(16).padStart(2, "0")).join("");
    if (hex !== chunk.sha256) throw new Error(`WASM chunk ${chunk.file}: checksum mismatch`);
    bytes.set(new Uint8Array(buffer), offset);
    offset += buffer.byteLength;
  }
  if (offset !== bytes.length) throw new Error("Incomplete WASM download");
  return bytes;
}
