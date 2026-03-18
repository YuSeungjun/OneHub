const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');

let pythonProcess = null;

function startPythonBackend() {
    let command;
    let args;

    // 포트가 사용 중일 가능성을 대비하여 시작 전에 프로세스 킬 시도
    if (process.platform === 'win32') {
        exec('for /f "tokens=5" %a in (\'netstat -aon ^| findstr :8000\') do taskkill /F /PID %a', () => { });
    }

    if (app.isPackaged) {
        command = path.join(process.resourcesPath, 'backend', 'main.exe');
        args = [];
    } else {
        const scriptPath = path.join(__dirname, '../backend/main.py');
        command = 'C:\\Users\\user\\anaconda3\\Scripts\\conda.exe';
        args = ['run', '-n', 'onehub', 'python', scriptPath];
    }

    pythonProcess = spawn(command, args, { shell: !app.isPackaged });

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
