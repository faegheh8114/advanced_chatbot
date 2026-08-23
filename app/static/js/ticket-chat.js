// Saipa Mashayekh 3299 — ticket conversation: polls for new messages and keeps the
// thread scrolled to the latest message without a full page reload.

(function () {
  const thread = document.getElementById("chat-thread");
  if (!thread) return;

  const ticketId = thread.dataset.ticketId;
  const currentUserId = parseInt(thread.dataset.currentUserId, 10);
  let lastId = parseInt(thread.dataset.lastMessageId || "0", 10);
  let polling = false;

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }

  function formatTime(iso) {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function renderMessage(m) {
    const isOwn = m.sender_id === currentUserId;
    const attachments = (m.attachments || [])
      .map(
        (a) =>
          `<a class="chat-attachment" href="/tickets/attachments/${a.id}">${a.is_image ? "🖼" : "📎"} ${escapeHtml(a.name)} <span class="text-faint">(${a.size})</span></a>`
      )
      .join("");

    const wrapper = document.createElement("div");
    wrapper.className = "chat-message" + (isOwn ? " own" : "") + (m.is_internal_note ? " note" : "");
    wrapper.innerHTML = `
      <span class="avatar avatar-sm" style="background:${m.sender_color}">${escapeHtml(m.sender_initials)}</span>
      <div class="chat-bubble-col">
        <div class="chat-bubble">${escapeHtml(m.body)}</div>
        ${attachments ? `<div class="chat-attachments">${attachments}</div>` : ""}
        <div class="chat-meta">
          <strong>${escapeHtml(m.sender_name)}</strong>
          ${m.is_internal_note ? '<span class="badge badge-amber">Internal note</span>' : ""}
          <span>${formatTime(m.created_at)}</span>
        </div>
      </div>`;
    thread.appendChild(wrapper);
  }

  function poll() {
    if (polling) return;
    polling = true;
    fetch(`/api/tickets/${ticketId}/messages?after_id=${lastId}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.messages && data.messages.length) {
          const wasNearBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 120;
          data.messages.forEach((m) => {
            renderMessage(m);
            lastId = Math.max(lastId, m.id);
          });
          if (wasNearBottom) thread.scrollTop = thread.scrollHeight;
        }
      })
      .catch(() => {})
      .finally(() => {
        polling = false;
      });
  }

  thread.scrollTop = thread.scrollHeight;
  setInterval(poll, 5000);

  // Selected-file chip preview for the composer.
  const fileInput = document.getElementById("composer-files");
  const chipRow = document.getElementById("file-chip-row");
  if (fileInput && chipRow) {
    fileInput.addEventListener("change", () => {
      chipRow.innerHTML = "";
      Array.from(fileInput.files)
        .slice(0, 5)
        .forEach((f) => {
          const chip = document.createElement("span");
          chip.className = "file-chip";
          chip.textContent = f.name;
          chipRow.appendChild(chip);
        });
    });
  }

  // Simple emoji picker.
  const emojiBtn = document.getElementById("emoji-btn");
  const emojiPanel = document.getElementById("emoji-panel");
  const composerBody = document.getElementById("composer-body");
  if (emojiBtn && emojiPanel && composerBody) {
    const emojis = ["🙂", "👍", "🙏", "✅", "❗", "📌", "⏳", "🎉", "👀", "❤️"];
    emojiPanel.innerHTML = emojis
      .map((e) => `<button type="button" class="icon-btn" data-emoji="${e}">${e}</button>`)
      .join("");
    emojiBtn.addEventListener("click", () => {
      emojiPanel.hidden = !emojiPanel.hidden;
    });
    emojiPanel.addEventListener("click", (e) => {
      const emoji = e.target.dataset.emoji;
      if (!emoji) return;
      composerBody.value += emoji;
      composerBody.focus();
      emojiPanel.hidden = true;
    });
  }
})();
