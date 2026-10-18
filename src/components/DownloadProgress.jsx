import { CheckCircle2, Volume2, VolumeX } from "lucide-react";

function bytes(value) {
  if (!Number.isFinite(value)) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  return `${value.toFixed(unit ? 1 : 0)} ${units[unit]}`;
}

function remaining(seconds, t) {
  if (!Number.isFinite(seconds)) return t.estimating;
  seconds = Math.ceil(seconds);
  return seconds < 60
    ? `${seconds}${t.seconds}`
    : `${Math.floor(seconds / 60)}${t.minutes} ${seconds % 60}${t.seconds}`;
}

export default function DownloadProgress({
  panelRef,
  job,
  t,
  connectionError,
  isProcessing,
  soundEnabled,
  onToggleSound,
}) {
  const complete = job.status === "success";
  const failed = job.status === "error" || connectionError;
  const status = connectionError
    ? t.backendError
    : job.status === "error"
      ? `${t.error}: ${job.message}`
      : t[job.status];
  const percent = Number.isFinite(job.progress)
    ? Math.max(0, Math.min(100, job.progress))
    : null;
  const stage = complete
    ? 3
    : job.status === "processing"
      ? 2
      : job.status === "downloading"
        ? 1
        : 0;
  const downloading = job.status === "downloading";
  return (
    <section
      ref={panelRef}
      className={`glass-panel status-panel ${failed ? "has-error" : ""} ${complete ? "is-complete" : ""}`}
      aria-label={t.progress}
    >
      <div className="progress-heading">
        <span className="progress-label">
          {complete ? (
            <CheckCircle2 size={18} />
          ) : (
            <span className="status-dot" />
          )}
          {t.progress}
        </span>
        <button
          type="button"
          className="sound-button"
          aria-pressed={soundEnabled}
          onClick={onToggleSound}
          title={soundEnabled ? t.soundOn : t.soundOff}
        >
          {soundEnabled ? <Volume2 size={17} /> : <VolumeX size={17} />}
          {soundEnabled ? t.soundOn : t.soundOff}
        </button>
      </div>
      <div className="progress-summary">
        <div className="progress-description">
          <p className="status-text" role="status">
            {status}
          </p>
          {downloading && (
            <span className="stream-label">
              {job.stream_kind === "audio" ? t.audioStream : t.videoStream}
            </span>
          )}
        </div>
        <strong className="progress-percent">
          {percent == null ? "…" : `${percent}%`}
        </strong>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={t.progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent ?? undefined}
        aria-valuetext={percent == null ? status : `${percent}%`}
      >
        <div
          className={`progress-fill ${isProcessing && percent == null ? "indeterminate" : ""}`}
          style={{ width: `${percent ?? 0}%` }}
        />
      </div>
      {downloading && (
        <div className="transfer-details">
          <span>
            {bytes(job.downloaded_bytes)} /{" "}
            {job.total_estimated && job.total_bytes ? "~" : ""}
            {bytes(job.total_bytes)}
          </span>
          <span>{bytes(job.speed)}/s</span>
          <span>
            {t.remaining} {remaining(job.eta, t)}
          </span>
        </div>
      )}
      <ol className="progress-stages">
        {[t.stagePrepare, t.stageDownload, t.stageProcess, t.stageSaved].map(
          (label, index) => (
            <li
              key={index}
              className={
                !failed && job.status !== "canceled" && index <= stage
                  ? "reached"
                  : ""
              }
              aria-current={
                isProcessing && index === stage ? "step" : undefined
              }
            >
              <span>{index < stage || complete ? "✓" : index + 1}</span>
              {label}
            </li>
          ),
        )}
      </ol>
      {complete && job.saved_path ? (
        <p className="saved-path" title={job.saved_path}>
          {t.savedTo} {job.saved_path}
        </p>
      ) : (
        isProcessing && <small>{t.progressHint}</small>
      )}
    </section>
  );
}
