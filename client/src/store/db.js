/**
 * Store wrapper that uses Electron IPC to communicate with electron-store
 * Falls back to localStorage in browser/development mode
 */

class Store {
  constructor() {
    // Check if running in Electron
    this.isElectron = window.electronStore !== undefined;

    if (!this.isElectron) {
      // Fallback to localStorage for development without Electron
      this.localData = this.loadFromLocalStorage();
    }
  }

  loadFromLocalStorage() {
    try {
      const stored = localStorage.getItem("browser_farm_data");
      return stored ? JSON.parse(stored) : this.getDefaultData();
    } catch (error) {
      console.error("Failed to load from localStorage:", error);
      return this.getDefaultData();
    }
  }

  saveToLocalStorage() {
    try {
      localStorage.setItem("browser_farm_data", JSON.stringify(this.localData));
    } catch (error) {
      console.error("Failed to save to localStorage:", error);
    }
  }

  getDefaultData() {
    return {
      servers: [],
      proxies: [],
      accounts: [],
      profiles: [],
      scripts: [], // NEW: Script Library storage
      settings: {
        homeScreenCount: 4,
        homeScreens: [],
      },
    };
  }

  async get(key) {
    if (this.isElectron) {
      return await window.electronStore.get(key);
    } else {
      return this.localData[key];
    }
  }

  async set(key, value) {
    if (this.isElectron) {
      await window.electronStore.set(key, value);
    } else {
      this.localData[key] = value;
      this.saveToLocalStorage();
    }
  }

  async delete(key) {
    if (this.isElectron) {
      await window.electronStore.delete(key);
    } else {
      delete this.localData[key];
      this.saveToLocalStorage();
    }
  }

  async clear() {
    if (this.isElectron) {
      await window.electronStore.clear();
    } else {
      this.localData = this.getDefaultData();
      this.saveToLocalStorage();
    }
  }

  async has(key) {
    if (this.isElectron) {
      return await window.electronStore.has(key);
    } else {
      return this.localData.hasOwnProperty(key);
    }
  }

  async getAll() {
    if (this.isElectron) {
      return await window.electronStore.getAll();
    } else {
      return this.localData;
    }
  }
}

const store = new Store();
export default store;
