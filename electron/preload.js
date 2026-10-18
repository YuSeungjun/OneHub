const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getBackendConfig: () => ipcRenderer.invoke("backend:config"),
  selectFolder: () => ipcRenderer.invoke("dialog:selectFolder"),
  getDefaultDownloadPath: () =>
    ipcRenderer.invoke("dialog:getDefaultDownloadPath"),
  platform: process.platform,
});
