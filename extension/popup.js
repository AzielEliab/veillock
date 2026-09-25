const lift = document.getElementById("lift");
const key = document.getElementById("key");
const save = document.getElementById("save");
const note = document.getElementById("note");

chrome.storage.local.get({ lifted: false, keyHex: "" }, (cfg) => {
  lift.checked = Boolean(cfg.lifted);
  key.value = String(cfg.keyHex || "");
});

save.addEventListener("click", () => {
  const keyHex = key.value.trim();
  if (keyHex && !/^[0-9a-fA-F]{64}$/.test(keyHex)) {
    note.textContent = "The key must be 64 hex characters, or empty to leave encryption off.";
    return;
  }
  chrome.storage.local.set({ lifted: lift.checked, keyHex }, () => {
    note.textContent = keyHex
      ? "Saved. Both browsers need this extension and this key. Encoded frames are AES-256-GCM. Reload the call tab."
      : "Saved. Encryption is off. The page still gets the veil until you lift it. Reload the call tab.";
  });
});
