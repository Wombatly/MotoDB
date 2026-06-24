// Kontextsensitive Hilfe: öffnet/schließt das seitliche Hilfe-Panel.
// Externe Datei wegen strenger CSP (kein Inline-Script erlaubt).
(function () {
  "use strict";

  var lastTrigger = null;

  function closeAll() {
    document.querySelectorAll("[data-help-panel]").forEach(function (panel) {
      panel.hidden = true;
    });
    document.querySelectorAll("[data-help-overlay]").forEach(function (ov) {
      ov.hidden = true;
    });
    document.body.classList.remove("help-open");
    if (lastTrigger) {
      lastTrigger.focus();
      lastTrigger = null;
    }
  }

  function open(key, trigger) {
    var panel = document.getElementById("help-" + key);
    if (!panel) {
      return;
    }
    closeAll();
    lastTrigger = trigger || null;
    panel.hidden = false;
    var overlay = document.querySelector("[data-help-overlay]");
    if (overlay) {
      overlay.hidden = false;
    }
    document.body.classList.add("help-open");
    var closeBtn = panel.querySelector("[data-help-close]");
    if (closeBtn) {
      closeBtn.focus();
    }
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-help-open]");
    if (trigger) {
      event.preventDefault();
      open(trigger.getAttribute("data-help-open"), trigger);
      return;
    }
    if (event.target.closest("[data-help-close]") || event.target.closest("[data-help-overlay]")) {
      closeAll();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && document.body.classList.contains("help-open")) {
      closeAll();
    }
  });
})();
