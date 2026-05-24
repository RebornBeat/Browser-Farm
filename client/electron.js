const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");

let Store;
try {
  Store = require("electron-store").default;
} catch (e) {
  Store = require("electron-store");
}

const isDev = process.argv.includes("--dev");

// Disable sandbox on Linux for development
if (process.platform === "linux") {
  app.commandLine.appendSwitch("no-sandbox");
}

// Initialize electron-store
const store = new Store({
  defaults: {
    servers: [],
    proxies: [],
    accounts: [],
    profiles: [],
    settings: {
      homeScreenCount: 4,
      homeScreens: [],
    },
  },
});

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
      sandbox: false, // Disable sandbox
    },
    backgroundColor: "#0f172a",
    show: false,
    frame: true,
    titleBarStyle: "default",
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:3000");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "build", "index.html"));
  }

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// IPC Handlers for Store
ipcMain.handle("store-get", (event, key) => {
  return store.get(key);
});

ipcMain.handle("store-set", (event, key, value) => {
  store.set(key, value);
  return true;
});

ipcMain.handle("store-delete", (event, key) => {
  store.delete(key);
  return true;
});

ipcMain.handle("store-clear", () => {
  store.clear();
  return true;
});

ipcMain.handle("store-has", (event, key) => {
  return store.has(key);
});

ipcMain.handle("store-get-all", () => {
  return store.store;
});

ipcMain.handle("get-app-path", () => {
  return app.getPath("userData");
});

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
