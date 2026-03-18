const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    selectFolder: () => ipcRenderer.invoke('dialog:selectFolder'),
    getDefaultDownloadPath: () => ipcRenderer.invoke('dialog:getDefaultDownloadPath')
});
