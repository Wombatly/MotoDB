async function syncPendingServices() {
  const services = await offlineDb.getServices();
  const checklistServices = await offlineDb.getChecklistServices();
  if (!services.length && !checklistServices.length) {
    showToast("Keine offenen Offline-Einträge.");
    return;
  }

  const response = await fetch("/api/sync", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content || "",
    },
    body: JSON.stringify({ services, checklist_services: checklistServices }),
  });

  if (!response.ok) {
    throw new Error("Sync fehlgeschlagen");
  }

  await offlineDb.clearServices();
  await offlineDb.clearChecklistServices();
  showToast(`${services.length + checklistServices.length} Offline-Eintrag synchronisiert.`);
}

document.getElementById("syncButton")?.addEventListener("click", async () => {
  try {
    await syncPendingServices();
  } catch (error) {
    showToast("Server nicht erreichbar. Sync später erneut starten.");
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
  data.motorrad_id = Number(form.dataset.motorradId);
  data.created_offline_at = new Date().toISOString();
  delete data.beleg;

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
