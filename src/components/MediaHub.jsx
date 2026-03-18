import React, { useState } from 'react';
import { Download, MonitorPlay, Music, XCircle } from 'lucide-react';

export default function MediaHub({ onDownload, t, downloadPath, onSelectPath, isProcessing, onCancel }) {
    const [url, setUrl] = useState('');
    const [format, setFormat] = useState('mp4');
    const [resolution, setResolution] = useState('1080p');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (url) {
            onDownload && onDownload(url, format, resolution);
        }
    };

    return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', marginTop: '0.5rem' }}>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1, overflowY: 'auto', paddingRight: '4px' }}>
                <div className="input-group">
                    <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>{t.youtubeUrl}</label>
                    <input
                        type="url"
                        placeholder="https://www.youtube.com/watch?v=..."
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        style={{
                            width: '100%', padding: '1rem', borderRadius: '12px',
                            border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.3)',
                            color: 'white', outline: 'none', transition: 'border-color 0.3s'
                        }}
                        required
                    />
                </div>

                <div style={{ display: 'flex', gap: '1rem' }}>
                    <div
                        onClick={() => setFormat('mp4')}
                        style={{
                            flex: 1, padding: '1rem', borderRadius: '12px', cursor: 'pointer',
                            border: `2px solid ${format === 'mp4' ? 'var(--accent-blue)' : 'rgba(255,255,255,0.1)'}`,
                            background: format === 'mp4' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(0,0,0,0.2)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                            transition: 'all 0.3s'
                        }}>
                        <MonitorPlay size={20} color={format === 'mp4' ? 'var(--accent-blue)' : 'var(--text-muted)'} />
                        <span style={{ color: format === 'mp4' ? 'white' : 'var(--text-muted)', fontWeight: '500' }}>{t.videoMp4}</span>
                    </div>

                    <div
                        onClick={() => setFormat('mp3')}
                        style={{
                            flex: 1, padding: '1rem', borderRadius: '12px', cursor: 'pointer',
                            border: `2px solid ${format === 'mp3' ? 'var(--accent-purple)' : 'rgba(255,255,255,0.1)'}`,
                            background: format === 'mp3' ? 'rgba(139, 92, 246, 0.1)' : 'rgba(0,0,0,0.2)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                            transition: 'all 0.3s'
                        }}>
                        <Music size={20} color={format === 'mp3' ? 'var(--accent-purple)' : 'var(--text-muted)'} />
                        <span style={{ color: format === 'mp3' ? 'white' : 'var(--text-muted)', fontWeight: '500' }}>{t.audioMp3}</span>
                    </div>
                </div>

                {format === 'mp4' && (
                    <div className="input-group">
                        <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>{t.resolution}</label>
                        <select
                            value={resolution}
                            onChange={(e) => setResolution(e.target.value)}
                            style={{
                                width: '100%', padding: '0.8rem', borderRadius: '12px',
                                border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.3)',
                                color: 'white', outline: 'none'
                            }}
                        >
                            <option value="4K" style={{ background: '#1e293b' }}>2160p (4K)</option>
                            <option value="1080p" style={{ background: '#1e293b' }}>1080p (FHD)</option>
                            <option value="720p" style={{ background: '#1e293b' }}>720p (HD)</option>
                        </select>
                    </div>
                )}

                <div className="input-group">
                    <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>{t.downloadPath}</label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <input
                            type="text"
                            value={downloadPath || t.defaultPath}
                            readOnly
                            style={{
                                flex: 1, padding: '0.8rem', borderRadius: '12px',
                                border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)',
                                color: 'var(--text-muted)', outline: 'none'
                            }}
                        />
                        <button
                            type="button"
                            onClick={onSelectPath}
                            style={{
                                padding: '0 1rem', borderRadius: '12px', cursor: 'pointer',
                                background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)',
                                color: 'white', fontWeight: '500', transition: 'background 0.2s'
                            }}
                            onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.2)'}
                            onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
                        >
                            {t.browse}
                        </button>
                    </div>
                </div>

                <div style={{ flex: 1 }}></div>

                {isProcessing ? (
                    <button
                        type="button"
                        onClick={onCancel}
                        style={{
                            padding: '1rem', borderRadius: '12px',
                            background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                            color: 'white', fontWeight: 'bold', border: 'none', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                            boxShadow: '0 4px 15px rgba(239, 68, 68, 0.4)', transition: 'transform 0.2s'
                        }}
                        onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                        onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                    >
                        <XCircle size={20} />
                        {t.cancel}
                    </button>
                ) : (
                    <button
                        type="submit"
                        style={{
                            padding: '1rem', borderRadius: '12px',
                            background: 'linear-gradient(135deg, var(--accent-blue), #2563eb)',
                            color: 'white', fontWeight: 'bold', border: 'none', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                            boxShadow: '0 4px 15px rgba(59, 130, 246, 0.4)', transition: 'transform 0.2s'
                        }}
                        onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                        onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                    >
                        <Download size={20} />
                        {t.extractMedia}
                    </button>
                )}
            </form>
        </div>
    );
}
