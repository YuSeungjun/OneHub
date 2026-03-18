import React, { useState } from 'react';
import { UploadCloud, FileText, FileImage, ArrowRight, XCircle } from 'lucide-react';

export default function DocHub({ onConvert, t, downloadPath, onSelectPath, isProcessing, onCancel }) {
    const [file, setFile] = useState(null);
    const [direction, setDirection] = useState('HWP_TO_WORD'); // HWP_TO_WORD or WORD_TO_HWP
    const [isDragging, setIsDragging] = useState(false);

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            setFile(e.dataTransfer.files[0]);
        }
    };

    const handleSubmit = () => {
        if (file) {
            onConvert && onConvert(file, direction);
        }
    };

    return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', marginTop: '0.5rem', overflowY: 'auto', paddingRight: '4px' }}>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginBottom: '1rem' }}>
                <div
                    onClick={() => setDirection('HWP_TO_WORD')}
                    style={{
                        padding: '0.8rem 1.5rem', borderRadius: '30px', cursor: 'pointer',
                        background: direction === 'HWP_TO_WORD' ? 'rgba(139, 92, 246, 0.2)' : 'rgba(0,0,0,0.2)',
                        border: `1px solid ${direction === 'HWP_TO_WORD' ? 'var(--accent-purple)' : 'rgba(255,255,255,0.1)'}`,
                        color: direction === 'HWP_TO_WORD' ? 'white' : 'var(--text-muted)',
                        display: 'flex', alignItems: 'center', gap: '0.5rem', transition: 'all 0.3s'
                    }}>
                    <FileImage size={18} /> HWP <ArrowRight size={14} /> Word
                </div>
                <div
                    onClick={() => setDirection('WORD_TO_HWP')}
                    style={{
                        padding: '0.8rem 1.5rem', borderRadius: '30px', cursor: 'pointer',
                        background: direction === 'WORD_TO_HWP' ? 'rgba(139, 92, 246, 0.2)' : 'rgba(0,0,0,0.2)',
                        border: `1px solid ${direction === 'WORD_TO_HWP' ? 'var(--accent-purple)' : 'rgba(255,255,255,0.1)'}`,
                        color: direction === 'WORD_TO_HWP' ? 'white' : 'var(--text-muted)',
                        display: 'flex', alignItems: 'center', gap: '0.5rem', transition: 'all 0.3s'
                    }}>
                    <FileText size={18} /> Word <ArrowRight size={14} /> HWP
                </div>
            </div>

            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                style={{
                    flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                    border: `2px dashed ${isDragging ? 'var(--accent-purple)' : 'rgba(255,255,255,0.2)'}`,
                    borderRadius: '20px', background: isDragging ? 'rgba(139, 92, 246, 0.05)' : 'rgba(0,0,0,0.2)',
                    transition: 'all 0.3s', marginBottom: '1.5rem', cursor: 'pointer'
                }}
                onClick={() => document.getElementById('fileUpload').click()}
            >
                <UploadCloud size={48} color={isDragging ? 'var(--accent-purple)' : 'var(--text-muted)'} style={{ marginBottom: '1rem' }} />
                {file ? (
                    <p style={{ color: 'white', fontWeight: '500', textAlign: 'center' }}>{file.name}</p>
                ) : (
                    <>
                        <p style={{ color: 'white', fontWeight: '500', marginBottom: '0.5rem' }}>{t.dragDrop}</p>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{t.clickBrowse}</p>
                    </>
                )}
                <input
                    id="fileUpload"
                    type="file"
                    style={{ display: 'none' }}
                    onChange={(e) => e.target.files && setFile(e.target.files[0])}
                    accept={direction === 'HWP_TO_WORD' ? '.hwp,.hwpx' : '.doc,.docx'}
                />
            </div>

            <div className="input-group" style={{ marginBottom: '1rem' }}>
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

            {isProcessing ? (
                <button
                    type="button"
                    onClick={onCancel}
                    style={{
                        padding: '1rem', borderRadius: '12px', flexShrink: 0,
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
                    onClick={handleSubmit}
                    disabled={!file}
                    style={{
                        padding: '1rem', borderRadius: '12px', flexShrink: 0,
                        background: file ? 'linear-gradient(135deg, var(--accent-purple), #7c3aed)' : 'rgba(255,255,255,0.1)',
                        color: file ? 'white' : 'var(--text-muted)', fontWeight: 'bold', border: 'none',
                        cursor: file ? 'pointer' : 'not-allowed',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                        boxShadow: file ? '0 4px 15px rgba(139, 92, 246, 0.4)' : 'none', transition: 'all 0.2s'
                    }}
                    onMouseOver={(e) => { if (file) e.currentTarget.style.transform = 'translateY(-2px)' }}
                    onMouseOut={(e) => { if (file) e.currentTarget.style.transform = 'translateY(0)' }}
                >
                    <UploadCloud size={20} />
                    {t.convertDoc}
                </button>
            )}

        </div>
    );
}
