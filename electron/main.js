const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn, exec, execSync } = require('child_process');

// 앱 중복 실행 방지 — 이미 실행 중이면 기존 창을 포커스
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
    app.quit();
}

let pythonProcess = null;

function startPythonBackend() {
    let command;
    let args;

    // 이전 main.exe가 남아있으면 확실히 죽이고 시작
    if (process.platform === 'win32') {
        try { execSync('taskkill /F /IM main.exe', { stdio: 'ignore' }); } catch (_) {}
    }

    if (app.isPackaged) {
        command = path.join(process.resourcesPath, 'backend', 'main.exe');
        args = [];
    } else {
        const scriptPath = path.join(__dirname, '../backend/main.py');
        command = 'python';
        args = [scriptPath];
    }

    pythonProcess = spawn(command, args, { shell: false });

    pythonProcess.stdout.on('data', (data) => {
        console.log(`Backend stdout: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`Backend stderr: ${data}`);
    });
}

function createWindow() {
    const win = new BrowserWindow({
        width: 1100,
        height: 750,
        autoHideMenuBar: true,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true
        }
    });

    if (!app.isPackaged) {
        win.loadURL('http://localhost:5173');
    } else {
        win.loadFile(path.join(process.resourcesPath, 'renderer', 'index.html'));
    }
}

app.whenReady().then(() => {
    ipcMain.handle('dialog:selectFolder', async () => {
        const result = await dialog.showOpenDialog({
            properties: ['openDirectory']
        });
        if (result.canceled) {
            return null;
        } else {
            return result.filePaths[0];
        }
    });

    ipcMain.handle('dialog:getDefaultDownloadPath', () => {
        return app.getPath('downloads');
    });

    // 두 번째 인스턴스가 실행되면 기존 창을 포커스
    app.on('second-instance', () => {
        const windows = BrowserWindow.getAllWindows();
        if (windows.length > 0) {
            if (windows[0].isMinimized()) windows[0].restore();
            windows[0].focus();
        }
    });

    startPythonBackend();
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('will-quit', () => {
    if (pythonProcess) {
        if (process.platform === 'win32') {
            exec(`taskkill /F /T /PID ${pythonProcess.pid}`);
            exec('taskkill /F /IM main.exe');
        } else {
            pythonProcess.kill();
        }
    }
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
