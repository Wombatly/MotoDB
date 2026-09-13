function currentUserId() {
  const value = document.body?.dataset.userId;
  return value ? Number(value) : null;
}

// Eintraege ohne user_id stammen aus aelteren Versionen und werden dem
// angemeldeten Nutzer zugerechnet, damit sie ueberhaupt synchronisierbar bleiben.
function belongsToCurrentUser(entry, userId) {
  return entry.user_id == null || entry.user_id === userId;
}

function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || "";
}

async function syncPendingServices({ manual = false } = {}) {
  const userId = currentUserId();
  if (userId === null) return;

  const allServices = await offlineDb.getServices();
  const allChecklistServices = await offlineDb.getChecklistServices();
  const pick = (entries) =>
    entries.filter((entry) => belongsToCurrentUser(entry, userId) && (manual || !entry.rejected_at));
  const services = pick(allServices);
  const checklistServices = pick(allChecklistServices);

  if (!services.length && !checklistServices.length) {
    if (manual) {
      const foreign = allServices.length + allChecklistServices.length;
      showToast(
        foreign
          ? "Keine eigenen Offline-Einträge. Einträge anderer Konten bleiben gespeichert."
          : "Keine offenen Offline-Einträge."
      );
    }
    return;
  }

  const response = await fetch("/api/sync", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
    body: JSON.stringify({ services, checklist_services: checklistServices }),
  });

  if (!response.ok) {
    throw new Error(`Sync fehlgeschlagen (${response.status})`);
  }

  const result = await response.json();
  const accepted = result.accepted || { services: [], checklist_services: [] };
  const rejected = result.rejected || { services: [], checklist_services: [] };
  const byIndex = (entries, indexes) => (indexes || []).map((index) => entries[index]).filter(Boolean);

  const acceptedServices = byIndex(services, accepted.services);
  const acceptedChecklists = byIndex(checklistServices, accepted.checklist_services);
  const rejectedServices = byIndex(services, rejected.services);
  const rejectedChecklists = byIndex(checklistServices, rejected.checklist_services);

  await offlineDb.deleteIds(offlineDb.STORES.services, acceptedServices.map((entry) => entry.local_id));
  await offlineDb.deleteIds(offlineDb.STORES.checklistServices, acceptedChecklists.map((entry) => entry.local_id));

  const acceptedCount = acceptedServices.length + acceptedChecklists.length;
  const rejectedCount = rejectedServices.length + rejectedChecklists.length;

  if (rejectedCount) {
    const discard =
      manual &&
      window.confirm(
        `${rejectedCount} Offline-Eintrag/-Einträge wurden vom Server abgelehnt ` +
          "(z. B. ungültige Angaben oder gelöschtes Motorrad). Sollen sie verworfen werden?"
      );
    if (discard) {
      await offlineDb.deleteIds(offlineDb.STORES.services, rejectedServices.map((entry) => entry.local_id));
      await offlineDb.deleteIds(offlineDb.STORES.checklistServices, rejectedChecklists.map((entry) => entry.local_id));
    } else {
      await offlineDb.markRejected(offlineDb.STORES.services, rejectedServices);
      await offlineDb.markRejected(offlineDb.STORES.checklistServices, rejectedChecklists);
    }
  }

  if (acceptedCount && rejectedCount) {
    showToast(`${acceptedCount} Eintrag/Einträge synchronisiert, ${rejectedCount} abgelehnt.`);
  } else if (acceptedCount) {
    showToast(`${acceptedCount} Offline-Eintrag/-Einträge synchronisiert.`);
  } else {
    showToast(`${rejectedCount} Offline-Eintrag/-Einträge wurden vom Server abgelehnt.`);
  }
}

document.getElementById("syncButton")?.addEventListener("click", async () => {
  try {
    await syncPendingServices({ manual: true });
  } catch (error) {
    showToast("Sync nicht möglich. Bist du angemeldet und online?");
  }
});

async function saveServiceFormOffline(form) {
  const receiptInput = form.querySelector('input[type="file"][name="beleg"]');
  if (receiptInput?.files?.length) {
    showToast("Belege können offline nicht gespeichert werden.");
    return;
  }

  form.querySelectorAll(".number-input").forEach((input) => {
    input.value = input.value.replace(/[^\d]/g, "");
  });
  const formData = new FormData(form);
  const data = Object.fromEntries(formData.entries());
  delete data.csrf_token;
  delete data.beleg;
  data.motorrad_id = Number(form.dataset.motorradId);
  data.user_id = currentUserId();
  data.created_offline_at = new Date().toISOString();

  const serviceType = data.service_art || "free";
  if (serviceType.startsWith("checklist:")) {
    const checklistId = serviceType.split(":")[1];
    data.checklist_id = Number(checklistId);
    data.completed_item_ids = formData.getAll(`checklist_erledigt_${checklistId}`);
    data.item_notes = {};
    for (const [key, value] of formData.entries()) {
      if (key.startsWith("checklist_anmerkung_") && value) {
        data.item_notes[key.replace("checklist_anmerkung_", "")] = value;
      }
    }
    await offlineDb.addChecklistService(data);
  } else {
    await offlineDb.addService(data);
  }

  showToast("Service offline gespeichert. Sync überträgt ihn später.");
  window.setTimeout(() => {
    window.location.href = `/motorrad/${data.motorrad_id}`;
  }, 500);
}

document.querySelector("[data-offline-service-form]")?.addEventListener("submit", async (event) => {
  if (navigator.onLine) {
    return;
  }

  event.preventDefault();
  const form = document.querySelector("[data-offline-service-form]");
  if (!form) return;
  await saveServiceFormOffline(form);
});

window.addEventListener("online", () => {
  syncPendingServices().catch(() => {});
});
