/**
 * Isolated-world bridge. The page script cannot read chrome.storage.
 * Default remains veil and no key until this message arrives.
 *
 * Author: Aziel Eliab.
 */
chrome.storage.local.get({ lifted: false, keyHex: "" }, (cfg) => {
  window.postMessage(
    { source: "veillock-bridge", lifted: Boolean(cfg.lifted), keyHex: String(cfg.keyHex || "") },
    "*"
  );
});
