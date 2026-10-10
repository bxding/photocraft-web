import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const script = readFileSync(new URL('../static/instance-notice.js', import.meta.url), 'utf8');
const key = 'photocraft-public-instance-dismissed';
const storage = () => {
  const data = new Map();
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) };
};

function browser(localStorage = storage(), sessionStorage = storage()) {
  const nodes = new Map();
  const button = { listeners: {}, addEventListener(type, fn) { this.listeners[type] = fn; } };
  const panel = { listeners: {}, addEventListener(type, fn) { this.listeners[type] = fn; } };
  const shadow = { innerHTML: '', querySelector: selector => selector === 'button' ? button : panel };
  const document = {
    getElementById: id => nodes.get(id),
    createElement: () => {
      const host = { attachShadow: () => shadow, remove: () => nodes.delete(host.id) };
      return host;
    },
    body: { append: host => nodes.set(host.id, host) },
  };
  const context = vm.createContext({ window: { localStorage, sessionStorage }, document });
  return {
    run: () => vm.runInContext(script, context),
    visible: () => nodes.size,
    close: () => button.listeners.click(),
    escape: () => panel.listeners.keydown({ key: 'Escape', stopPropagation() {} }),
    content: () => shadow.innerHTML,
  };
}

test('notice stays dismissed on reload and a new browser session', () => {
  const local = storage();
  const first = browser(local);
  first.run();
  assert.equal(first.visible(), 1);
  assert.match(first.content(), /https:\/\/github.com\/storytold\/photocraft/);
  assert.match(first.content(), /6 hours/);
  first.close();
  assert.equal(first.visible(), 0);
  assert.equal(local.getItem(key), '1');
  const reopened = browser(local); // New DOM and sessionStorage; same browser profile.
  reopened.run();
  assert.equal(reopened.visible(), 0);
});

test('Escape dismisses the notice when interacting with it', () => {
  const page = browser();
  page.run();
  page.escape();
  assert.equal(page.visible(), 0);
});

test('blocked storage does not prevent showing or closing the notice', () => {
  const blocked = {
    getItem() { throw new Error('Storage blocked'); },
    setItem() { throw new Error('Storage blocked'); },
  };
  const page = browser(blocked, blocked);
  page.run();
  assert.equal(page.visible(), 1);
  page.close();
  assert.equal(page.visible(), 0);
});

test('injecting the script twice does not duplicate the window', () => {
  const page = browser();
  page.run();
  page.run();
  assert.equal(page.visible(), 1);
});
