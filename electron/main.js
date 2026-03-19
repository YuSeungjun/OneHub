const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, execFile } = require('child_process');

const logFile = path.join(app.getPath('userData'), 'onehub_debug.log');
function log(msg) {
    const line = `[${new Date().toISOString()}] ${msg}\n`;
    try { fs.appendFileSync(logFile, line); } catch (_) {}
}

// 앱 중복 실행 방지 — 이미 실행 중이면 기존 창을 포커스
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
    app.quit();
}

let pythonProcess = null;

const taskkillPath = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe');

function killProcess(name) {
    try {
        execFile(taskkillPath, ['/F', '/IM', name], { stdio: 'ignore' });
    } catch (_) {}
}

function startPythonBackend() {
    let command;
    let args;
    let cwd;

    // 이전 백엔드가 남아있으면 확실히 죽이고 시작
    if (process.platform === 'win32') {
        killProcess('onehub_backend.exe');
    }

    if (app.isPackaged) {
        command = path.join(process.resourcesPath, 'backend', 'onehub_backend.exe');
        args = [];
        cwd = app.getPath('userData');
    } else {
        const projectRoot = path.join(__dirname, '..');
        command = process.platform === 'win32' ? 'uv.cmd' : 'uv';
        args = ['run', 'python', path.join(projectRoot, 'backend', 'main.py')];
        cwd = projectRoot;
    }

    log(`Spawning backend: command=${command} args=${JSON.stringify(args)} cwd=${cwd}`);
    log(`Command exists: ${fs.existsSync(command)}`);

    const shell = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'cmd.exe');
    log(`Using shell: ${shell}, exists: ${fs.existsSync(shell)}`);

    pythonProcess = spawn(command, args, {
        cwd: cwd,
        stdio: ['pipe', 'pipe', 'pipe'],
        shell: shell,
    });

    pythonProcess.stdout.on('data', (data) => {
        log(`stdout: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        log(`stderr: ${data}`);
    });

    pythonProcess.on('error', (err) => {
        log(`Spawn error: ${err.message}`);
    });

    pythonProcess.on('exit', (code, signal) => {
        log(`Backend exited: code=${code} signal=${signal}`);
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
            execFile(taskkillPath, ['/F', '/T', '/PID', String(pythonProcess.pid)], { stdio: 'ignore' });
            killProcess('onehub_backend.exe');
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
