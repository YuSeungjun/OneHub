const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, execFile, execFileSync } = require('child_process');
const net = require('net');

let logFile = null;
function _ensureLogFile() {
    if (!logFile) {
        try { logFile = path.join(app.getPath('userData'), 'onehub_debug.log'); } catch (_) {}
    }
}
function log(msg) {
    const line = `[${new Date().toISOString()}] ${msg}\n`;
    _ensureLogFile();
    if (logFile) {
        try { fs.appendFileSync(logFile, line); } catch (_) {}
    }
    try { process.stdout.write(line); } catch (_) {}
}

// 앱 중복 실행 방지 — 이미 실행 중이면 기존 창을 포커스
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
    app.quit();
}

let pythonProcess = null;
let backendStopping = false;  // 앱 종료 중 재시작 방지

const BACKEND_PORT = 8000;
const taskkillPath = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe');

function killProcess(name) {
    try {
        execFileSync(taskkillPath, ['/F', '/IM', name], { stdio: 'ignore' });
    } catch (_) {}
}

/** 포트 8000을 점유 중인 프로세스를 찾아서 죽인다 */
function killPortHolder(port) {
    if (process.platform !== 'win32') return;
    try {
        const result = execFileSync('netstat', ['-ano'], { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'ignore'] });
        const lines = result.split('\n');
        const pids = new Set();
        for (const line of lines) {
            // 127.0.0.1:8000 또는 0.0.0.0:8000 LISTENING 상태인 PID 수집
            if (line.includes(`:${port}`) && line.includes('LISTENING')) {
                const parts = line.trim().split(/\s+/);
                const pid = parts[parts.length - 1];
                if (pid && pid !== '0') pids.add(pid);
            }
        }
        for (const pid of pids) {
            log(`Killing PID ${pid} holding port ${port}`);
            try {
                execFileSync(taskkillPath, ['/F', '/T', '/PID', pid], { stdio: 'ignore' });
            } catch (_) {}
        }
    } catch (e) {
        log(`killPortHolder error: ${e.message}`);
    }
}

/** 포트가 열려있는지 확인 (백엔드가 살아있는지 헬스체크) */
function isPortOpen(port) {
    return new Promise((resolve) => {
        const sock = new net.Socket();
        sock.setTimeout(1000);
        sock.once('connect', () => { sock.destroy(); resolve(true); });
        sock.once('timeout', () => { sock.destroy(); resolve(false); });
        sock.once('error', () => { sock.destroy(); resolve(false); });
        sock.connect(port, '127.0.0.1');
    });
}

function startPythonBackend() {
    if (backendStopping) return;

    let command;
    let args;
    let cwd;
    let useShell = false;

    // 이전 백엔드가 남아있으면 확실히 죽이고 시작
    if (process.platform === 'win32') {
        killProcess('onehub_backend.exe');
        killPortHolder(BACKEND_PORT);
    }

    if (app.isPackaged) {
        command = path.join(process.resourcesPath, 'backend', 'onehub_backend.exe');
        args = [];
        cwd = app.getPath('userData');
        useShell = false;  // 패키지된 exe는 shell 불필요
    } else {
        const projectRoot = path.join(__dirname, '..');
        command = process.platform === 'win32' ? 'uv.cmd' : 'uv';
        args = ['run', 'python', path.join(projectRoot, 'backend', 'main.py')];
        cwd = projectRoot;
        useShell = true;  // .cmd 파일은 shell 필요
    }

    // cwd가 없으면 생성
    try { fs.mkdirSync(cwd, { recursive: true }); } catch (_) {}

    log(`Spawning backend: command=${command} args=${JSON.stringify(args)} cwd=${cwd} shell=${useShell}`);
    log(`Command exists: ${fs.existsSync(command)}`);

    const spawnOpts = {
        cwd: cwd,
        stdio: ['pipe', 'pipe', 'pipe'],
    };
    if (useShell) {
        spawnOpts.shell = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'cmd.exe');
    }

    pythonProcess = spawn(command, args, spawnOpts);

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
        pythonProcess = null;
        // 비정상 종료 시 자동 재시작 (최대 3회)
        if (!backendStopping && code !== 0) {
            backendRetries = (backendRetries || 0) + 1;
            if (backendRetries <= 3) {
                log(`Auto-restarting backend (attempt ${backendRetries}/3) in 2s...`);
                setTimeout(() => startPythonBackend(), 2000);
            } else {
                log(`Backend failed ${backendRetries} times, giving up.`);
            }
        }
    });

    // 재시작 카운터는 성공적으로 서버가 뜨면 리셋
    const healthCheck = setInterval(async () => {
        if (backendStopping || !pythonProcess) {
            clearInterval(healthCheck);
            return;
        }
        const alive = await isPortOpen(BACKEND_PORT);
        if (alive) {
            backendRetries = 0;  // 서버가 정상 동작 — 재시작 카운터 리셋
            clearInterval(healthCheck);
            log('Backend health check passed — server is listening.');
        }
    }, 2000);
}

let backendRetries = 0;

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
    backendStopping = true;  // 재시작 방지
    if (pythonProcess) {
        if (process.platform === 'win32') {
            try { execFileSync(taskkillPath, ['/F', '/T', '/PID', String(pythonProcess.pid)], { stdio: 'ignore' }); } catch (_) {}
            killProcess('onehub_backend.exe');
        } else {
            pythonProcess.kill();
        }
        pythonProcess = null;
    }
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
