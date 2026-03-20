import React, { useState, useEffect, useRef } from 'react';
import { Youtube, FileText, Globe } from 'lucide-react';
import MediaHub from './components/MediaHub';
import DocHub from './components/DocHub';
import { translations } from './locales';
import './index.css';

function App() {
  const [activeMode, setActiveMode] = useState('media'); // 'media' or 'doc'
  const [lang, setLang] = useState('ko');
  const [platform] = useState(() => window.electronAPI?.platform || 'win32');
  const t = translations[lang];
  const [status, setStatus] = useState(t.ready);
  const [progress, setProgress] = useState(0);
  const [downloadPath, setDownloadPath] = useState('');
  const isProcessing = progress > 0 && progress < 100;
  const abortControllerRef = useRef(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (status === translations[lang === 'ko' ? 'en' : 'ko'].ready) {
      setStatus(t.ready);
    }
  }, [lang]);

  useEffect(() => {
    const initPath = async () => {
      if (window.electronAPI && window.electronAPI.getDefaultDownloadPath) {
        const p = await window.electronAPI.getDefaultDownloadPath();
        if (p) setDownloadPath(p);
      }
    };
    initPath();
  }, []);

  // 백엔드가 아직 안 떴으면 자동 재시도 (최대 15초)
  const fetchWithRetry = async (url, options, retries = 10) => {
    for (let i = 0; i < retries; i++) {
      try {
        return await fetch(url, options);
      } catch (err) {
        if (err.name === 'AbortError') throw err;
        if (i === retries - 1) throw err;
        await new Promise(r => setTimeout(r, 1500));
      }
    }
  };

  const handleCancel = async () => {
    cancelledRef.current = true;
    // 1. 프론트엔드 fetch 요청 중단
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    // 2. 백엔드에 취소 신호 전송 (yt-dlp 프로세스 종료 + 부분 파일 삭제)
    try {
      await fetch('http://127.0.0.1:8000/media/cancel', { method: 'POST' });
    } catch (_) { /* 무시 */ }
    setProgress(0);
    setStatus(t.canceled);
  };

  const toggleMode = () => {
    if (isProcessing) {
      alert(lang === 'ko' ? '현재 작업이 진행 중입니다. 잠시 후 시도해주세요.' : 'Task is currently processing. Please try again later.');
      return;
    }
    setActiveMode(prev => prev === 'media' ? 'doc' : 'media');
  };

  const handleMediaDownload = async (url, format, resolution) => {
    cancelledRef.current = false;
    setStatus(`${t.extracting.replace('{format}', format.toUpperCase())} ${t.fromYoutube}`);
    setProgress(15);
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetchWithRetry('http://127.0.0.1:8000/media/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, format, resolution, download_path: downloadPath }),
        signal: abortControllerRef.current.signal
      });
      if (cancelledRef.current) return;
      const data = await response.json();
      if (cancelledRef.current) return;
      if (response.ok && data.status === 'success') {
        setProgress(100);
        setStatus(t.extractionComplete);
      } else if (data.status === 'canceled') {
        setStatus(t.canceled);
        setProgress(0);
      } else {
        const errorMsg = data.message || (data.detail ? JSON.stringify(data.detail) : 'Unknown error');
        setStatus(`${t.error}: ${errorMsg}`);
        setProgress(0);
      }
    } catch (err) {
      if (cancelledRef.current) return;
      if (err.name === 'AbortError') {
        setStatus(t.canceled);
      } else {
        setStatus(t.backendError);
      }
      setProgress(0);
    }
    setTimeout(() => { if (progress === 100) setProgress(0); }, 3000);
  };

  const handleDocConvert = async (file, direction) => {
    const dirText = direction === 'HWP_TO_WORD' ? 'Word' : 'HWP';
    setStatus(`${t.converting.replace('{file}', file.name)} ${dirText} ${t.to}`);
    setProgress(20);
    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('direction', direction);
      formData.append('save_path', downloadPath || '');

      const response = await fetchWithRetry('http://127.0.0.1:8000/doc/convert', {
        method: 'POST',
        body: formData,
        signal: abortControllerRef.current.signal
      });
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        setProgress(100);
        setStatus(t.conversionComplete);
      } else {
        const errorMsg = data.message || (data.detail ? JSON.stringify(data.detail) : 'Unknown error');
        setStatus(`${t.error}: ${errorMsg}`);
        setProgress(0);
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setStatus(t.canceled);
      } else {
        setStatus(t.backendError);
      }
      setProgress(0);
    }
    setTimeout(() => { if (progress === 100) setProgress(0); }, 3000);
  };

  return (
    <div className="app-container">
      {/* Language Toggle */}
      <div style={{ position: 'absolute', top: '2rem', left: '2rem', zIndex: 100 }}>
        <button
          onClick={() => setLang(lang === 'ko' ? 'en' : 'ko')}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)',
            padding: '8px 16px', borderRadius: '20px', color: 'white',
            cursor: 'pointer', fontWeight: '500', transition: 'all 0.3s'
          }}
          onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.2)'}
          onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
        >
          <Globe size={18} />
          {lang === 'ko' ? 'English' : '한국어'}
        </button>
      </div>

      <div className="glass-panel main-content">

        {/* Media Hub Section */}
        <div className={`hub-section media-hub ${activeMode === 'media' ? 'active' : ''}`}>
          <div className="hub-header">
            <h1 className="hub-title">
              <Youtube style={{ display: 'inline-block', marginRight: '8px', verticalAlign: 'middle' }} size={36} />
              {t.mediaHubTitle}
            </h1>
            <p className="hub-subtitle">{t.mediaHubSub}</p>
          </div>
          <MediaHub
            onDownload={handleMediaDownload}
            t={t}
            downloadPath={downloadPath}
            isProcessing={activeMode === 'media' && isProcessing}
            onCancel={handleCancel}
            onSelectPath={async () => {
              if (window.electronAPI && window.electronAPI.selectFolder) {
                const folderPath = await window.electronAPI.selectFolder();
                if (folderPath) setDownloadPath(folderPath);
              }
            }}
          />
        </div>

        {/* Central Toggle */}
        <div className="toggle-container">
          <div
            className={`toggle-switch ${activeMode}`}
            onClick={toggleMode}
            title={`Switch to ${activeMode === 'media' ? 'Doc Hub' : 'Media Hub'}`}
          >
            <div className="toggle-thumb">
              {activeMode === 'media' ? <Youtube size={20} /> : <FileText size={20} />}
            </div>
          </div>
        </div>

        {/* Doc Hub Section */}
        <div className={`hub-section doc-hub ${activeMode === 'doc' ? 'active' : ''}`}>
          <div className="hub-header">
            <h1 className="hub-title">
              <FileText style={{ display: 'inline-block', marginRight: '8px', verticalAlign: 'middle' }} size={32} />
              {t.docHubTitle}
            </h1>
            <p className="hub-subtitle">{platform === 'darwin' ? t.docHubSubMac : t.docHubSub}</p>
          </div>
          <DocHub
            onConvert={handleDocConvert}
            t={t}
            downloadPath={downloadPath}
            isProcessing={activeMode === 'doc' && isProcessing}
            onCancel={handleCancel}
            platform={platform}
            onSelectPath={async () => {
              if (window.electronAPI && window.electronAPI.selectFolder) {
                const folderPath = await window.electronAPI.selectFolder();
                if (folderPath) setDownloadPath(folderPath);
              }
            }}
          />
        </div>
      </div>

      {/* Global Status Bar */}
      <div className="glass-panel status-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '12px', height: '12px', borderRadius: '50%',
            backgroundColor: progress > 0 && progress < 100 ? '#facc15' : '#4ade80'
          }}></div>
          <span className="status-text">{status}</span>
        </div>
        <div className="progress-container">
          <div className="progress-fill" style={{ width: `${progress}%` }}></div>
        </div>
        {progress > 0 && <span style={{ fontSize: '0.875rem', fontWeight: '500', marginLeft: '1rem' }}>{progress}%</span>}
      </div>
    </div>
  );
}

export default App;
