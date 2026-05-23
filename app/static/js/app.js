function showToast(message) {
  const toastElement = document.getElementById("appToast");
  const toastBody = document.getElementById("appToastBody");
  if (!toastElement || !toastBody) return;
  toastBody.textContent = message;
  toastElement.classList.add("toast--visible");
  window.clearTimeout(showToast.hideTimer);
  showToast.hideTimer = window.setTimeout(() => {
    toastElement.classList.remove("toast--visible");
  }, 3200);
}

document.querySelector("[data-toast-close]")?.addEventListener("click", () => {
  document.getElementById("appToast")?.classList.remove("toast--visible");
});

document.querySelector("[data-menu-toggle]")?.addEventListener("click", (event) => {
  const button = event.currentTarget;
  const menu = document.querySelector("[data-menu]");
  const isOpen = menu?.classList.toggle("nav-actions--open");
  button.setAttribute("aria-expanded", isOpen ? "true" : "false");
});

document.addEventListener("click", (event) => {
  const menu = document.querySelector("[data-menu]");
  const toggle = document.querySelector("[data-menu-toggle]");
  if (!menu || !toggle || !menu.classList.contains("nav-actions--open")) return;
  if (menu.contains(event.target) || toggle.contains(event.target)) return;
  menu.classList.remove("nav-actions--open");
  toggle.setAttribute("aria-expanded", "false");
});

document.querySelector("[data-technical-motorcycle-select]")?.addEventListener("change", (event) => {
  window.location.href = `/technik?motorrad_id=${event.target.value}`;
});

document.querySelector("[data-service-type]")?.addEventListener("change", (event) => {
  const value = event.target.value;
  const checklistId = value.startsWith("checklist:") ? value.split(":")[1] : null;
  document.querySelector("[data-service-checklists]")?.toggleAttribute("hidden", !checklistId);
  document.querySelectorAll("[data-free-service-field]").forEach((field) => {
    field.toggleAttribute("hidden", Boolean(checklistId));
  });
  document.querySelectorAll("[data-service-checklist]").forEach((section) => {
    section.toggleAttribute("hidden", section.dataset.serviceChecklist !== checklistId);
  });
});

document.querySelector("[data-toggle-sheet]")?.addEventListener("click", () => {
  const sheet = document.querySelector("[data-sheet]");
  if (!sheet) return;
  sheet.toggleAttribute("hidden");
});

document.querySelectorAll("[data-autosave-sheet] .spec-input").forEach((input) => {
  input.addEventListener("change", () => {
    input.form?.requestSubmit();
  });
});

function normalizeNumberInput(input) {
  const raw = input.value.replace(/[^\d]/g, "");
  if (!raw) {
    input.value = "";
    return;
  }
  input.value = Number(raw).toLocaleString("de-DE");
}

document.querySelectorAll(".number-input").forEach((input) => {
  normalizeNumberInput(input);
  input.addEventListener("blur", () => normalizeNumberInput(input));
});

document.querySelectorAll("[data-image-fallback]").forEach((image) => {
  const showFallback = () => {
    image.hidden = true;
    image.nextElementSibling?.removeAttribute("hidden");
  };
  if (image.complete && image.naturalWidth === 0) {
    showFallback();
  } else {
    image.addEventListener("error", showFallback, { once: true });
  }
});

document.querySelectorAll("form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    const message = form.dataset.confirm;
    if (message && !window.confirm(message)) {
      event.preventDefault();
      return;
    }
    form.querySelectorAll(".number-input").forEach((input) => {
      input.value = input.value.replace(/[^\d]/g, "");
    });
  });
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/service-worker.js");
}
