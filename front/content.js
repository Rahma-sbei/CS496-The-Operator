// Runs on mail.google.com. When the side panel reports that a change was made,
// press Gmail's own Refresh button so the inbox on screen matches the real mailbox.
chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || msg.type !== "refresh-inbox") return;
  const btn = document.querySelector('div[aria-label="Refresh"][role="button"], div[act="20"]');
  if (!btn) return;
  ["mousedown", "mouseup", "click"].forEach((type) =>
    btn.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }))
  );
});
