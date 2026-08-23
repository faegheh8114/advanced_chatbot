// Saipa Mashayekh 3299 — shared UI behaviors: toasts, confirm dialogs, flash auto-dismiss.

function showToast(message, type) {
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const el = document.createElement("div");
  el.className = "toast" + (type ? " toast-" + type : "");
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.25s ease";
    setTimeout(() => el.remove(), 250);
  }, 4000);
}

document.addEventListener("DOMContentLoaded", () => {
  // Auto-dismiss server-rendered flash banners after a few seconds.
  document.querySelectorAll(".flash-stack .flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease, max-height 0.4s ease";
      el.style.opacity = "0";
    }, 5000);
  });

  // Close notification dropdown when clicking outside of it.
  document.addEventListener("click", (e) => {
    const dropdown = document.getElementById("notif-dropdown");
    const bellBtn = document.getElementById("notif-bell-btn");
    if (!dropdown || dropdown.hidden) return;
    if (!dropdown.contains(e.target) && e.target !== bellBtn) {
      dropdown.hidden = true;
    }
  });

  // Lightweight confirm dialog for destructive actions.
  // Usage: <form data-confirm="Delete this user? This cannot be undone.">
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (form.dataset.confirmed === "true") return;
      e.preventDefault();
      openConfirmDialog(form.dataset.confirm, () => {
        form.dataset.confirmed = "true";
        form.submit();
      });
    });
  });
});

function openConfirmDialog(message, onConfirm) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <div class="modal-title">Please confirm</div>
      <div class="modal-body"></div>
      <div class="modal-actions">
        <button type="button" class="btn btn-secondary" data-action="cancel">Cancel</button>
        <button type="button" class="btn btn-danger" data-action="confirm">Confirm</button>
      </div>
    </div>`;
  backdrop.querySelector(".modal-body").textContent = message;
  document.body.appendChild(backdrop);

  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop || e.target.dataset.action === "cancel") {
      backdrop.remove();
    } else if (e.target.dataset.action === "confirm") {
      backdrop.remove();
      onConfirm();
    }
  });
}
