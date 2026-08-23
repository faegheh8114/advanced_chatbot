// Saipa Mashayekh 3299 — notification bell: polls unread count and renders the dropdown list.

(function () {
  const bellBtn = document.getElementById("notif-bell-btn");
  const dropdown = document.getElementById("notif-dropdown");
  const list = document.getElementById("notif-dropdown-list");
  const countEl = document.getElementById("notif-count");
  const markAllBtn = document.getElementById("mark-all-read-btn");
  if (!bellBtn) return;

  function timeAgo(iso) {
    const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
    if (seconds < 86400) return Math.floor(seconds / 3600) + "h ago";
    return Math.floor(seconds / 86400) + "d ago";
  }

  function render(data) {
    countEl.textContent = data.unread_count;
    countEl.hidden = data.unread_count === 0;

    if (!data.items.length) {
      list.innerHTML = '<div class="empty-hint-sm">You\'re all caught up — no notifications yet.</div>';
      return;
    }

    list.innerHTML = data.items
      .map((n) => {
        const href = n.ticket_id ? `/notifications/${n.id}/open` : "#";
        return `<a href="${href}" class="notif-item ${n.is_read ? "" : "unread"}" data-id="${n.id}">
          <div class="notif-item-title">${escapeHtml(n.title)}</div>
          ${n.body ? `<div class="notif-item-body">${escapeHtml(n.body)}</div>` : ""}
          <div class="notif-item-time">${timeAgo(n.created_at)}</div>
        </a>`;
      })
      .join("");
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }

  function refresh() {
    fetch("/api/notifications/summary")
      .then((r) => r.json())
      .then(render)
      .catch(() => {});
  }

  bellBtn.addEventListener("click", () => {
    dropdown.hidden = !dropdown.hidden;
    if (!dropdown.hidden) refresh();
  });

  if (markAllBtn) {
    markAllBtn.addEventListener("click", () => {
      fetch("/notifications/mark-all-read", {
        method: "POST",
        headers: { "X-CSRFToken": window.CSRF_TOKEN },
      }).then(refresh);
    });
  }

  refresh();
  setInterval(refresh, 30000);
})();
