const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const { randomBytes } = require("node:crypto");
const { spawn, execFileSync } = require("node:child_process");
const { waitForBackendPort, startupErrorMessage } = require("./backend-startup");

const isWindows = process.platform === "win32";
let backend;
let backendConfig;
let quitting = false;

function log(message) {
  try {
    fs.appendFileSync(
      path.join(app.getPath("userData"), "onehub_debug.log"),
      `${new Date().toISOString()} ${message}\n`,
    );
  } catch (error) {
    console.error(error);
  }
}

async function startBackend() {
  const startedAt = Date.now();
  const root = path.join(__dirname, "..");
  const command = app.isPackaged
    ? path.join(
        process.resourcesPath,
        "backend",
        isWindows ? "onehub_backend.exe" : "onehub_backend",
      )
    : path.join(root, ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
  const node = app.isPackaged
    ? path.join(
        process.resourcesPath,
        "runtime",
        isWindows ? "node.exe" : "node",
      )
    : process.env.npm_node_execpath;
  fs.mkdirSync(app.getPath("userData"), { recursive: true });
  log(`Starting OneHub ${app.getVersion()}: packaged=${app.isPackaged}, backend=${command}`);
  if (!fs.existsSync(command))
    throw new Error("다운로드 서비스 실행 파일을 찾을 수 없습니다.");
  if (app.isPackaged && !fs.existsSync(node))
    throw new Error("유튜브 다운로드에 필요한 런타임 파일을 찾을 수 없습니다.");
  const token = randomBytes(32).toString("hex");
  backend = spawn(
    command,
    app.isPackaged ? [] : [path.join(root, "backend/main.py")],
    {
      cwd: app.isPackaged ? app.getPath("userData") : root,
      windowsHide: true,
      detached: !isWindows,
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        PYTHONUTF8: "1",
        PYTHONUNBUFFERED: "1",
        ONEHUB_PORT: "0",
        ONEHUB_API_TOKEN: token,
        ...(node ? { ONEHUB_NODE_PATH: node } : {}),
      },
    },
  );
  log(`Backend process: pid=${backend.pid}`);
  backend.once("exit", (code, signal) => {
    log(`Backend exited: code=${code}, signal=${signal}`);
    if (!quitting && backendConfig)
      dialog.showErrorBox(
        "OneHub",
        "다운로드 서비스가 종료되었습니다. 앱을 다시 실행해 주세요.",
      );
  });
  backend.stderr.on("data", (data) => log(data.toString()));
  const url = await waitForBackendPort(backend, { log });
  backend.stdout.on("data", (data) => log(data.toString()));
  backend.stdout.resume();
  log(`Backend port ready after ${Date.now() - startedAt} ms: ${url}`);
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      const response = await fetch(url, {
        headers: { "X-OneHub-Token": token },
        signal: AbortSignal.timeout(1000),
      });
      if (response.ok && (await response.json()).app === "onehub") {
        log(`Backend healthy after ${Date.now() - startedAt} ms`);
        return { url, token };
      }
    } catch {
      /* uvicorn is still starting. */
    }
    if (backend.exitCode !== null)
      throw new Error("백엔드를 시작하지 못했습니다.");
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("다운로드 서비스에 연결하지 못했습니다.");
}

function createWindow() {
  const win = new BrowserWindow({
    title: "OneHub · YouTube",
    width: 920,
    height: 820,
    minWidth: 540,
    minHeight: 680,
    autoHideMenuBar: true,
    backgroundColor: "#0f172a",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (event) => event.preventDefault());
  if (app.isPackaged)
    win.loadFile(path.join(process.resourcesPath, "renderer/index.html"));
  else win.loadURL("http://localhost:5173");
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => {
    const win = BrowserWindow.getAllWindows()[0];
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });
  app.whenReady().then(async () => {
    ipcMain.handle("backend:config", () => backendConfig);
    ipcMain.handle("dialog:getDefaultDownloadPath", () =>
      app.getPath("downloads"),
    );
    ipcMain.handle("dialog:selectFolder", async () => {
      const result = await dialog.showOpenDialog({
        properties: ["openDirectory", "createDirectory"],
      });
      return result.canceled ? null : result.filePaths[0];
    });
    try {
      backendConfig = await startBackend();
      createWindow();
    } catch (error) {
      log(error.stack || error.message);
      dialog.showErrorBox(
        "OneHub 시작 오류",
        startupErrorMessage(error, {
          packaged: app.isPackaged,
          logPath: path.join(app.getPath("userData"), "onehub_debug.log"),
        }),
      );
      app.quit();
    }
    app.on("activate", () => {
      if (backendConfig && !BrowserWindow.getAllWindows().length)
        createWindow();
    });
  });
}

app.on("before-quit", (event) => {
  if (quitting || !backendConfig || backend?.exitCode !== null) return;
  event.preventDefault();
  quitting = true;
  // Cancel the owned job and clean temporary files before stopping the server.
  fetch(`${backendConfig.url}/shutdown`, {
    method: "POST",
    headers: { "X-OneHub-Token": backendConfig.token },
    signal: AbortSignal.timeout(12000),
  })
    .catch((error) => log(`Graceful shutdown: ${error.message}`))
    .finally(() => app.quit());
});

app.on("will-quit", () => {
  quitting = true;
  if (!backend?.pid || backend.exitCode !== null) return;
  try {
    if (isWindows)
      execFileSync(
        path.join(
          process.env.SystemRoot || "C:\\Windows",
          "System32/taskkill.exe",
        ),
        ["/F", "/T", "/PID", String(backend.pid)],
        { stdio: "ignore", windowsHide: true },
      );
    else process.kill(-backend.pid, "SIGTERM");
  } catch (error) {
    log(`Backend shutdown: ${error.message}`);
  }
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
