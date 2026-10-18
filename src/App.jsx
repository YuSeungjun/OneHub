import { useEffect, useRef, useState } from "react";
import { Globe, Youtube } from "lucide-react";
import MediaHub from "./components/MediaHub";
import DownloadProgress from "./components/DownloadProgress";
import { prepareCompletionSound, playCompletionSound } from "./completionSound";
import { translations } from "./locales";

const activeStates = new Set([
  "starting",
  "downloading",
  "processing",
  "retrying",
  "canceling",
]);

async function requestApi(config, route, body) {
  const response = await fetch(`${config.url}${route}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(config.token ? { "X-OneHub-Token": config.token } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(15000),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join(" ")
      : data.detail;
    throw new Error(data.message || detail || `HTTP ${response.status}`);
  }
  return data;
}

export default function App() {
  const [lang, setLang] = useState("ko");
  const [config, setConfig] = useState(null);
  const [downloadPath, setDownloadPath] = useState("");
  const [job, setJob] = useState({ status: "ready", progress: 0 });
  const [connectionError, setConnectionError] = useState(false);
  const submitting = useRef(false);
  const notifiedJob = useRef(null);
  const progressPanel = useRef(null);
  const [soundEnabled, setSoundEnabled] = useState(() => {
    try {
      return localStorage.getItem("onehub-completion-sound") !== "off";
    } catch {
      return true;
    }
  });
  const t = translations[lang];
  const isProcessing = activeStates.has(job.status);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      window.electronAPI?.getBackendConfig() || {
        url: "http://127.0.0.1:8000",
        token: "",
      },
      window.electronAPI?.getDefaultDownloadPath() || "",
    ])
      .then(([backend, folder]) => {
        if (mounted) {
          setConfig(backend);
          setDownloadPath(folder);
        }
      })
      .catch(() => {
        if (mounted) setConnectionError(true);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    if (job.status !== "success" || !job.id || notifiedJob.current === job.id)
      return;
    notifiedJob.current = job.id;
    if (soundEnabled) void playCompletionSound().catch(() => {});
  }, [job.id, job.status, soundEnabled]);

  function toggleSound() {
    const enabled = !soundEnabled;
    setSoundEnabled(enabled);
    try {
      localStorage.setItem("onehub-completion-sound", enabled ? "on" : "off");
    } catch {
      /* The setting still works for this session. */
    }
    if (enabled) void prepareCompletionSound();
  }

  useEffect(() => {
    if (!config || !job.id || !isProcessing) return;
    let stopped = false;
    let timer;
    async function poll() {
      try {
        const next = await requestApi(config, `/media/status/${job.id}`);
        if (!stopped) {
          setJob(next);
          setConnectionError(false);
        }
      } catch {
        // Retain the active job during temporary connection failures.
        if (!stopped) setConnectionError(true);
      }
      if (!stopped) timer = setTimeout(poll, 700);
    }
    timer = setTimeout(poll, 200);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [config, job.id, isProcessing]);

  async function download(url, format, resolution) {
    if (!config || submitting.current || isProcessing) return;
    submitting.current = true;
    progressPanel.current?.scrollIntoView({
      block: "start",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
    if (soundEnabled) void prepareCompletionSound();
    setConnectionError(false);
    setJob({ status: "starting", progress: null });
    try {
      setJob(
        await requestApi(config, "/media/download", {
          url: url.trim(),
          format,
          resolution,
          download_path: downloadPath,
        }),
      );
    } catch (error) {
      setJob({ status: "error", progress: 0, message: error.message });
    } finally {
      submitting.current = false;
    }
  }

  async function cancel() {
    if (!job.id || job.status === "canceling") return;
    try {
      setJob(await requestApi(config, `/media/cancel/${job.id}`, {}));
    } catch {
      setConnectionError(true);
    }
  }

  async function selectPath() {
    try {
      const folder = await window.electronAPI?.selectFolder();
      if (folder) setDownloadPath(folder);
    } catch (error) {
      setJob({ status: "error", progress: 0, message: error.message });
    }
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <span className="brand">
          OneHub <span>YouTube</span>
        </span>
        <button
          className="language-button"
          onClick={() => setLang(lang === "ko" ? "en" : "ko")}
        >
          <Globe size={16} />
          {lang === "ko" ? "English" : "한국어"}
        </button>
      </header>
      <DownloadProgress
        panelRef={progressPanel}
        job={job}
        t={t}
        connectionError={connectionError}
        isProcessing={isProcessing}
        soundEnabled={soundEnabled}
        onToggleSound={toggleSound}
      />
      <main className="glass-panel main-content">
        <div className="hub-header">
          <div className="youtube-icon">
            <Youtube size={32} />
          </div>
          <h1>{t.mediaHubTitle}</h1>
          <p>{t.mediaHubSub}</p>
        </div>
        <MediaHub
          t={t}
          onDownload={download}
          downloadPath={downloadPath}
          onSelectPath={selectPath}
          canSelectPath={Boolean(window.electronAPI?.selectFolder)}
          isProcessing={isProcessing}
          canDownload={Boolean(config)}
          onCancel={cancel}
          canCancel={Boolean(job.id) && job.status !== "canceling"}
        />
      </main>
    </div>
  );
}
