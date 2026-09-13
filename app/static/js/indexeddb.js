const offlineDb = {
  STORES: {
    services: "pendingServices",
    checklistServices: "pendingChecklistServices",
  },

  open() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open("motorcycle-service", 2);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains("pendingServices")) {
          db.createObjectStore("pendingServices", {
            keyPath: "local_id",
            autoIncrement: true,
          });
        }
        if (!db.objectStoreNames.contains("pendingChecklistServices")) {
          db.createObjectStore("pendingChecklistServices", {
            keyPath: "local_id",
            autoIncrement: true,
          });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  },

  async transaction(storeName, mode, work) {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, mode);
      const result = work(tx.objectStore(storeName));
      tx.oncomplete = () => resolve(result && "result" in result ? result.result : undefined);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  },

  add(storeName, entry) {
    return this.transaction(storeName, "readwrite", (store) => store.add(entry));
  },

  getAll(storeName) {
    return this.transaction(storeName, "readonly", (store) => store.getAll());
  },

  // Entfernt die Eintraege mit den angegebenen local_ids (z. B. nach Bestaetigung durch den Server).
  deleteIds(storeName, ids) {
    if (!ids.length) return Promise.resolve();
    return this.transaction(storeName, "readwrite", (store) => {
      ids.forEach((id) => store.delete(id));
    });
  },

  // Markiert Eintraege als vom Server abgelehnt; der automatische Sync ueberspringt sie danach.
  markRejected(storeName, entries) {
    if (!entries.length) return Promise.resolve();
    const stamp = new Date().toISOString();
    return this.transaction(storeName, "readwrite", (store) => {
      entries.forEach((entry) => store.put({ ...entry, rejected_at: stamp }));
    });
  },

  // Kompatibilitaets-Aliase fuer bestehende Aufrufer.
  addService(service) {
    return this.add(this.STORES.services, service);
  },
  getServices() {
    return this.getAll(this.STORES.services);
  },
  addChecklistService(service) {
    return this.add(this.STORES.checklistServices, service);
  },
  getChecklistServices() {
    return this.getAll(this.STORES.checklistServices);
  },
};
