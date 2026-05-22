const offlineDb = {
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

  async addService(service) {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("pendingServices", "readwrite");
      tx.objectStore("pendingServices").add(service);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  },

  async getServices() {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("pendingServices", "readonly");
      const request = tx.objectStore("pendingServices").getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  },

  async clearServices() {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("pendingServices", "readwrite");
      tx.objectStore("pendingServices").clear();
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  },

  async addChecklistService(service) {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("pendingChecklistServices", "readwrite");
      tx.objectStore("pendingChecklistServices").add(service);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  },

  async getChecklistServices() {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("pendingChecklistServices", "readonly");
      const request = tx.objectStore("pendingChecklistServices").getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  },

  async clearChecklistServices() {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("pendingChecklistServices", "readwrite");
      tx.objectStore("pendingChecklistServices").clear();
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  },
};
