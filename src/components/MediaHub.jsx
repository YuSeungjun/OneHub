import { useState } from "react";
import { Download, Folder, MonitorPlay, Music, XCircle } from "lucide-react";

export default function MediaHub({
  onDownload,
  t,
  downloadPath,
  onSelectPath,
  canSelectPath,
  isProcessing,
  onCancel,
  canCancel,
  canDownload,
}) {
  const [url, setUrl] = useState("");
  const [format, setFormat] = useState("mp4");
  const [resolution, setResolution] = useState("1080p");
  function submit(event) {
    event.preventDefault();
    if (url.trim() && !isProcessing) onDownload(url, format, resolution);
  }
  return (
    <form onSubmit={submit} className="media-form">
      <fieldset disabled={isProcessing}>
        <div className="input-group">
          <label htmlFor="youtube-url">{t.youtubeUrl}</label>
          <input
            id="youtube-url"
            type="url"
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            required
          />
          <small>{t.singleVideo}</small>
        </div>
        <div className="format-options" role="group" aria-label={t.format}>
          <button
            type="button"
            aria-pressed={format === "mp4"}
            className={`format-button ${format === "mp4" ? "selected" : ""}`}
            onClick={() => setFormat("mp4")}
          >
            <MonitorPlay size={21} />
            {t.videoMp4}
          </button>
          <button
            type="button"
            aria-pressed={format === "mp3"}
            className={`format-button ${format === "mp3" ? "selected" : ""}`}
            onClick={() => setFormat("mp3")}
          >
            <Music size={21} />
            {t.audioMp3}
          </button>
        </div>
        {format === "mp4" && (
          <div className="input-group">
            <label htmlFor="resolution">{t.resolution}</label>
            <select
              id="resolution"
              value={resolution}
              onChange={(event) => setResolution(event.target.value)}
            >
              <option value="4K">2160p (4K)</option>
              <option value="1080p">1080p (FHD)</option>
              <option value="720p">720p (HD)</option>
            </select>
          </div>
        )}
        <div className="input-group">
          <label htmlFor="download-path">{t.downloadPath}</label>
          <div className="path-row">
            <input
              id="download-path"
              value={downloadPath || t.defaultPath}
              readOnly
            />
            <button
              type="button"
              className="browse-button"
              onClick={onSelectPath}
              disabled={!canSelectPath}
              title={!canSelectPath ? t.desktopOnly : undefined}
            >
              <Folder size={18} />
              {t.browse}
            </button>
          </div>
        </div>
      </fieldset>
      {isProcessing ? (
        <button
          type="button"
          className="action-button cancel-button"
          onClick={onCancel}
          disabled={!canCancel}
        >
          <XCircle size={20} />
          {t.cancel}
        </button>
      ) : (
        <button
          type="submit"
          className="action-button"
          disabled={!canDownload || !url.trim()}
        >
          <Download size={20} />
          {t.extractMedia}
        </button>
      )}
    </form>
  );
}
