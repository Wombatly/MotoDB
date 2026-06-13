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

const themeSelect = document.getElementById("themeSelect");
if (themeSelect && window.__motodbTheme) {
  themeSelect.value = window.__motodbTheme.get();
  themeSelect.addEventListener("change", () => {
    window.__motodbTheme.set(themeSelect.value);
  });
}

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

document.querySelectorAll("[data-nav-select]").forEach((select) => {
  select.addEventListener("change", () => {
    window.location.href = `${select.dataset.navSelect}?motorrad_id=${select.value}`;
  });
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

const detailTabs = Array.from(document.querySelectorAll("[data-tab]"));
if (detailTabs.length) {
  const panels = Array.from(document.querySelectorAll("[data-panel]"));
  const activateTab = (name) => {
    const match = detailTabs.find((tab) => tab.dataset.tab === name);
    if (!match) return;
    detailTabs.forEach((tab) => {
      tab.setAttribute("aria-selected", tab === match ? "true" : "false");
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.panel !== name;
    });
  };
  detailTabs.forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });
  const hash = window.location.hash.replace("#tab-", "");
  if (hash) activateTab(hash);
}

document.querySelector("[data-add-checklist-item]")?.addEventListener("click", () => {
  const builder = document.querySelector("[data-checklist-builder]");
  const template = document.querySelector("[data-checklist-row-template]");
  if (!builder || !template) return;
  const row = template.content.firstElementChild.cloneNode(true);
  builder.append(row);
  row.querySelector("input, textarea")?.focus();
});

document.querySelectorAll("[data-sheet] .spec-group").forEach((group) => {
  group.removeAttribute("open");
});

const imageManager = document.querySelector("[data-image-manager]");
if (imageManager) {
  const slides = Array.from(imageManager.querySelectorAll("[data-image-manager-slide]"));
  const currentLabel = imageManager.querySelector("[data-image-manager-current]");
  let activeIndex = slides.findIndex((slide) => slide.classList.contains("is-active"));
  if (activeIndex < 0) activeIndex = 0;

  const renderImageManager = (index) => {
    if (!slides.length) return;
    activeIndex = (index + slides.length) % slides.length;
    slides.forEach((slide, slideIndex) => {
      const isActive = slideIndex === activeIndex;
      slide.hidden = !isActive;
      slide.classList.toggle("is-active", isActive);
    });
    if (currentLabel) {
      currentLabel.textContent = String(activeIndex + 1);
    }
  };

  imageManager.querySelector("[data-image-manager-prev]")?.addEventListener("click", () => {
    renderImageManager(activeIndex - 1);
  });

  imageManager.querySelector("[data-image-manager-next]")?.addEventListener("click", () => {
    renderImageManager(activeIndex + 1);
  });

  renderImageManager(activeIndex);
}

const galleryViewer = document.querySelector("[data-gallery]");
if (galleryViewer) {
  const slides = Array.from(galleryViewer.querySelectorAll("[data-gallery-slide]"));
  const thumbs = Array.from(galleryViewer.querySelectorAll("[data-gallery-thumb]"));
  const currentLabel = galleryViewer.querySelector("[data-gallery-current]");
  let activeIndex = 0;

  const renderGallery = (index) => {
    if (!slides.length) return;
    activeIndex = (index + slides.length) % slides.length;
    slides.forEach((slide, slideIndex) => {
      const isActive = slideIndex === activeIndex;
      slide.hidden = !isActive;
      slide.classList.toggle("is-active", isActive);
    });
    thumbs.forEach((thumb, thumbIndex) => {
      thumb.classList.toggle("is-active", thumbIndex === activeIndex);
    });
    if (currentLabel) {
      currentLabel.textContent = String(activeIndex + 1);
    }
  };

  const closeGallery = () => {
    galleryViewer.hidden = true;
    galleryViewer.setAttribute("aria-hidden", "true");
    document.body.classList.remove("body--modal-open");
  };

  const openGallery = (index) => {
    renderGallery(index);
    galleryViewer.hidden = false;
    galleryViewer.setAttribute("aria-hidden", "false");
    document.body.classList.add("body--modal-open");
  };

  document.querySelectorAll("[data-gallery-open]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      openGallery(Number(trigger.dataset.galleryIndex || 0));
    });
  });

  galleryViewer.querySelectorAll("[data-gallery-close]").forEach((trigger) => {
    trigger.addEventListener("click", closeGallery);
  });

  galleryViewer.querySelector("[data-gallery-prev]")?.addEventListener("click", () => {
    renderGallery(activeIndex - 1);
  });

  galleryViewer.querySelector("[data-gallery-next]")?.addEventListener("click", () => {
    renderGallery(activeIndex + 1);
  });

  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      renderGallery(Number(thumb.dataset.galleryThumb || 0));
    });
  });

  document.addEventListener("keydown", (event) => {
    if (galleryViewer.hidden) return;
    if (event.key === "Escape") closeGallery();
    if (event.key === "ArrowLeft") renderGallery(activeIndex - 1);
    if (event.key === "ArrowRight") renderGallery(activeIndex + 1);
  });
}

document.querySelectorAll("[data-autosave-sheet] .spec-input").forEach((input) => {
  input.addEventListener("change", () => {
    input.form?.requestSubmit();
  });
});

function persistSheetOrder(form) {
  if (!form || !form.dataset.reorderUrl) return;
  const ids = Array.from(form.querySelectorAll("[data-spec-id]")).map((row) => row.dataset.specId);
  const token = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");
  fetch(form.dataset.reorderUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token || "" },
    body: JSON.stringify({ order: ids }),
  }).catch(() => {});
}

function moveSheetElement(element, selector, direction) {
  let sibling = direction === "up" ? element.previousElementSibling : element.nextElementSibling;
  while (sibling && !sibling.matches(selector)) {
    sibling = direction === "up" ? sibling.previousElementSibling : sibling.nextElementSibling;
  }
  if (!sibling) return false;
  if (direction === "up") element.parentNode.insertBefore(element, sibling);
  else element.parentNode.insertBefore(sibling, element);
  return true;
}

document.querySelectorAll("[data-move-spec]").forEach((button) => {
  button.addEventListener("click", () => {
    const row = button.closest("[data-spec-row]");
    if (row && moveSheetElement(row, "[data-spec-row]", button.dataset.moveSpec)) {
      persistSheetOrder(button.closest("[data-autosave-sheet]"));
    }
  });
});

document.querySelectorAll("[data-move-category]").forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const group = button.closest("[data-spec-category]");
    if (group && moveSheetElement(group, "[data-spec-category]", button.dataset.moveCategory)) {
      persistSheetOrder(button.closest("[data-autosave-sheet]"));
    }
  });
});

function normalizeNumberInput(input) {
  const raw = input.value.replace(/[^\d]/g, "");
  if (!raw) {
    input.value = "";
    return;
  }
  const suffix = input.dataset.numberSuffix ? ` ${input.dataset.numberSuffix}` : "";
  input.value = `${Number(raw).toLocaleString("de-DE")}${suffix}`;
}

document.querySelectorAll(".number-input").forEach((input) => {
  normalizeNumberInput(input);
  input.addEventListener("focus", () => {
    input.value = input.value.replace(/[^\d]/g, "");
  });
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
