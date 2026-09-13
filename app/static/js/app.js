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

function wireAutosaveInput(input) {
  input.addEventListener("change", () => {
    input.form?.requestSubmit();
  });
}

document.querySelectorAll("[data-autosave-sheet] .spec-input").forEach(wireAutosaveInput);

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

function initSpecMenus(form) {
  if (!form) return;
  let panel = null;
  let openToggle = null;
  let armedCleanup = null;

  function closeMenu() {
    if (panel) panel.remove();
    panel = null;
    if (openToggle) openToggle.setAttribute("aria-expanded", "false");
    openToggle = null;
  }

  function disarmMove() {
    if (armedCleanup) armedCleanup();
    armedCleanup = null;
  }

  // Zieht `item` innerhalb seiner Geschwister (die `selector` matchen) frei,
  // bis der Zeiger losgelassen wird; danach wird die neue Reihenfolge gespeichert.
  function startDrag(item, selector) {
    const container = item.parentNode;
    let moved = false;
    item.classList.add("is-dragging");

    const onMove = (moveEvent) => {
      if (moveEvent.cancelable) moveEvent.preventDefault();
      moved = true;
      const y = moveEvent.clientY;
      const edge = 60;
      if (y < edge) window.scrollBy(0, -12);
      else if (y > window.innerHeight - edge) window.scrollBy(0, 12);
      const siblings = Array.from(container.children).filter((node) => node !== item && node.matches(selector));
      let placed = false;
      for (const sibling of siblings) {
        const rect = sibling.getBoundingClientRect();
        if (y < rect.top + rect.height / 2) {
          container.insertBefore(item, sibling);
          placed = true;
          break;
        }
      }
      if (!placed && siblings.length) container.appendChild(item);
    };

    const onUp = () => {
      item.classList.remove("is-dragging");
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onUp);
      if (moved) persistSheetOrder(form);
    };

    document.addEventListener("pointermove", onMove, { passive: false });
    document.addEventListener("pointerup", onUp);
    document.addEventListener("pointercancel", onUp);
  }

  // "Verschieben" aus dem Menü versetzt `triggerEl` in einen markierten
  // Zustand; der naechste Zeigerdruck darauf startet das freie Verschieben
  // von `item` innerhalb von `selector`. Ein Klick daneben oder Escape bricht ab.
  function armMove(triggerEl, item, selector) {
    disarmMove();
    triggerEl.classList.add("is-move-armed");

    const onPointerDown = (event) => {
      event.preventDefault();
      event.stopPropagation();
      // Verhindert, dass der abschliessende Klick z. B. ein <summary> umschaltet.
      triggerEl.addEventListener(
        "click",
        (clickEvent) => {
          clickEvent.preventDefault();
          clickEvent.stopPropagation();
        },
        { capture: true, once: true }
      );
      disarmMove();
      startDrag(item, selector);
    };
    triggerEl.addEventListener("pointerdown", onPointerDown);

    const onOutsideClick = (event) => {
      if (triggerEl.contains(event.target)) return;
      disarmMove();
    };
    const onKeydown = (event) => {
      if (event.key === "Escape") disarmMove();
    };
    // Verzoegert registrieren, damit der Klick auf "Verschieben" selbst
    // nicht sofort als Klick ausserhalb zaehlt.
    const timer = window.setTimeout(() => {
      document.addEventListener("click", onOutsideClick, true);
      document.addEventListener("keydown", onKeydown);
    }, 0);

    armedCleanup = () => {
      triggerEl.classList.remove("is-move-armed");
      triggerEl.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("click", onOutsideClick, true);
      document.removeEventListener("keydown", onKeydown);
      window.clearTimeout(timer);
    };

    showToast("Zum Verschieben ziehen – oder woanders klicken zum Abbrechen.");
  }

  function renameCategory(group) {
    const nameSpan = group.querySelector("[data-spec-category-name]");
    const current = nameSpan?.textContent.trim() || "Allgemein";
    const next = window.prompt("Neuer Name für diese Kategorie:", current);
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed || trimmed === current) return;
    group.querySelectorAll('[data-spec-row] input[name="kategorie"]').forEach((input) => {
      input.value = trimmed;
    });
    if (nameSpan) nameSpan.textContent = trimmed;
    form.requestSubmit();
  }

  function renameField(row) {
    const nameSpan = row.querySelector("[data-spec-field-name]");
    const nameInput = row.querySelector('input[name="name"]');
    const current = nameInput?.value || nameSpan?.textContent.trim() || "";
    const next = window.prompt("Neue Bezeichnung für dieses Feld:", current);
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed || trimmed === current) return;
    if (nameInput) nameInput.value = trimmed;
    if (nameSpan) nameSpan.textContent = trimmed;
    form.requestSubmit();
  }

  function createFieldRow(category) {
    const row = document.createElement("div");
    row.className = "spec-row spec-row--new";
    row.innerHTML = `
      <input type="hidden" name="kategorie" value="">
      <input type="hidden" name="quelle" value="">
      <input type="hidden" name="einheit" value="">
      <button type="button" class="spec-row__save" data-spec-save aria-label="Feld speichern" title="Speichern">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"></path><path d="M17 21v-8H7v8"></path><path d="M7 3v5h8"></path></svg>
      </button>
      <div class="spec-row__body">
        <input class="spec-input" name="name" placeholder="Bezeichnung" aria-label="Neues Feld: Bezeichnung">
        <div class="spec-row__value">
          <input class="spec-input spec-input--value" name="wert" placeholder="Wert" aria-label="Neues Feld: Wert">
        </div>
      </div>
    `;
    row.querySelector('input[name="kategorie"]').value = category;

    // Bewusst KEIN Autosave-on-change hier: bei einem frischen, leeren Feld
    // wuerde schon der Fokuswechsel von Bezeichnung zu Wert das Formular
    // abschicken, bevor der Wert eingetragen ist - und die Zeile wird dann
    // verworfen, da save_technical_specs() Name+Wert zusammen braucht.
    // Stattdessen erst auf expliziten Speichern-Klick (oder Enter) senden.
    const nameInput = row.querySelector('input[name="name"]');
    const valueInput = row.querySelector('input[name="wert"]');
    const saveButton = row.querySelector("[data-spec-save]");

    const trySave = () => {
      if (!nameInput.value.trim() || !valueInput.value.trim()) {
        showToast("Bitte Bezeichnung und Wert ausfüllen.");
        (nameInput.value.trim() ? valueInput : nameInput).focus();
        return;
      }
      form.requestSubmit();
    };

    saveButton.addEventListener("click", trySave);
    [nameInput, valueInput].forEach((input) => {
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          trySave();
        }
      });
    });

    return row;
  }

  function addField(group) {
    group.open = true;
    const list = group.querySelector(".spec-list");
    if (!list) return;
    const category = group.querySelector("[data-spec-category-name]")?.textContent.trim() || "Allgemein";
    const row = createFieldRow(category);
    list.append(row);
    row.querySelector('input[name="name"]')?.focus();
  }

  function addFieldAfter(row) {
    const category = row.querySelector('input[name="kategorie"]')?.value || "Allgemein";
    const newRow = createFieldRow(category);
    row.after(newRow);
    newRow.querySelector('input[name="name"]')?.focus();
  }

  function openMenu(toggle) {
    const kind = toggle.dataset.specMenuToggle;
    let items;

    if (kind === "category") {
      const group = toggle.closest("[data-spec-category]");
      if (!group) return;
      items = [
        {
          label: "Verschieben",
          action: () => armMove(group.querySelector("summary"), group, "[data-spec-category]"),
        },
        { label: "Umbenennen", action: () => renameCategory(group) },
        { label: "Feld hinzufügen", action: () => addField(group) },
      ];
    } else {
      const row = toggle.closest("[data-spec-row]");
      if (!row) return;
      items = [
        { label: "Verschieben", action: () => armMove(row, row, "[data-spec-row]") },
        { label: "Umbenennen", action: () => renameField(row) },
        { label: "Feld hinzufügen", action: () => addFieldAfter(row) },
      ];
    }

    panel = document.createElement("div");
    panel.className = "spec-menu-panel";
    panel.setAttribute("role", "menu");

    items.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "menu-item";
      button.textContent = item.label;
      button.setAttribute("role", "menuitem");
      button.addEventListener("click", () => {
        closeMenu();
        item.action();
      });
      panel.append(button);
    });

    document.body.append(panel);
    const rect = toggle.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    let left = rect.right - panelRect.width;
    left = Math.max(8, Math.min(left, window.innerWidth - panelRect.width - 8));
    let top = rect.bottom + 6;
    if (top + panelRect.height > window.innerHeight - 8) {
      top = rect.top - panelRect.height - 6;
    }
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;

    toggle.setAttribute("aria-expanded", "true");
    openToggle = toggle;
  }

  form.querySelectorAll("[data-spec-menu-toggle]").forEach((toggle) => {
    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (openToggle === toggle) {
        closeMenu();
      } else {
        closeMenu();
        openMenu(toggle);
      }
    });
    toggle.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle.click();
      }
    });
  });

  document.addEventListener("click", (event) => {
    if (!panel) return;
    if (panel.contains(event.target) || openToggle?.contains(event.target)) return;
    closeMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });
  window.addEventListener("scroll", closeMenu, true);
  window.addEventListener("resize", closeMenu);
}

initSpecMenus(document.querySelector("[data-autosave-sheet][data-reorder-url]"));

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

// Offline-Fallback-Seite: sobald die Verbindung zurueck ist, die Startseite laden.
if (document.querySelector("[data-offline-retry]")) {
  window.addEventListener("online", () => {
    window.location.href = "/";
  });
}
