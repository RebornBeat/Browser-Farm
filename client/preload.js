const { contextBridge, ipcRenderer } = require("electron");

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld("electronStore", {
  get: (key) => ipcRenderer.invoke("store-get", key),
  set: (key, value) => ipcRenderer.invoke("store-set", key, value),
  delete: (key) => ipcRenderer.invoke("store-delete", key),
  clear: () => ipcRenderer.invoke("store-clear"),
  has: (key) => ipcRenderer.invoke("store-has", key),
  getAll: () => ipcRenderer.invoke("store-get-all"),
});

contextBridge.exposeInMainWorld("electronAPI", {
  getAppPath: () => ipcRenderer.invoke("get-app-path"),
});
