(() => {
  const key = "photocraft-public-instance-dismissed";
  const stores = [];
  for (const name of ["localStorage", "sessionStorage"]) {
    try {
      const store = window[name];
      if (store.getItem(key) === "1") return;
      stores.push(store);
    } catch {
      // Storage may be unavailable in private or restricted browsing contexts.
    }
  }
  if (document.getElementById("photocraft-instance-notice")) return;

  const host = document.createElement("div");
  host.id = "photocraft-instance-notice";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      section {
        position: fixed; right: 20px; bottom: 20px; z-index: 2147483647;
        box-sizing: border-box; width: min(380px, calc(100vw - 40px));
        padding: 22px; border: 1px solid #555; border-radius: 12px;
        background: #25252b; color: #eee;
        box-shadow: 0 8px 32px #0006;
        font: 14px/1.6 system-ui, sans-serif;
      }
      h2 { margin: 0 36px 10px 0; font-size: 16px; line-height: 1.4; }
      p { margin: 0; color: #d3d3dc; }
      a { color: #a8c7ff; text-underline-offset: 3px; }
      button {
        position: absolute; top: 10px; right: 10px; width: 36px; height: 36px;
        border: 0; border-radius: 6px; background: transparent; color: #ddd;
        font: 24px/1 system-ui, sans-serif; cursor: pointer;
      }
      button:hover { background: #ffffff18; }
      button:focus-visible, a:focus-visible { outline: 2px solid #a8c7ff; outline-offset: 3px; }
    </style>
    <section role="dialog" aria-labelledby="instance-title" aria-describedby="instance-description">
      <button type="button" aria-label="Dismiss instance notice">&times;</button>
      <h2 id="instance-title">About this instance</h2>
      <p id="instance-description">This is a public instance of the WebAssembly version of
        <a href="https://github.com/storytold/photocraft" target="_blank" rel="noopener noreferrer">PhotoCraft</a>.
        Automatic deployments are scheduled every 6 hours using the latest version from the repository.</p>
    </section>
  `;

  function dismiss() {
    for (const store of stores) {
      try { store.setItem(key, "1"); } catch { /* Keep dismissal functional without storage. */ }
    }
    host.remove();
  }
  root.querySelector("button").addEventListener("click", dismiss);
  const panel = root.querySelector("section");
  // Keep interactions with the notice from triggering editor shortcuts/tools.
  for (const type of ["click", "pointerdown", "pointerup", "keydown", "keyup"]) {
    panel.addEventListener(type, event => {
      event.stopPropagation();
      if (type === "keydown" && event.key === "Escape") dismiss();
    });
  }
  document.body.append(host);
})();
