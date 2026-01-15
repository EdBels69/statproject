import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadDataset } from '../../lib/api';
import ResearchFlowNav from '../components/ResearchFlowNav';

export default function Upload() {
    const navigate = useNavigate();
    const [dragActive, setDragActive] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    const [fileName, setFileName] = useState(null);

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleUpload(e.dataTransfer.files[0]);
        }
    };

    const handleChange = (e) => {
        e.preventDefault();
        if (e.target.files && e.target.files[0]) {
            handleUpload(e.target.files[0]);
        }
    };

    const handleUpload = async (file) => {
        setUploading(true);
        setError(null);
        setFileName(file.name);
        try {
            const data = await uploadDataset(file);
            navigate(`/profile/${data.id}`, {
                state: {
                    profile: data.profile,
                    filename: data.filename
                }
            });
        } catch (err) {
            setError(err.message);
        } finally {
            setUploading(false);
        }
    };

    return (
        <div style={{ maxWidth: '600px', margin: '0 auto' }} className="animate-fadeIn">
            <ResearchFlowNav active="data" className="mb-6" />
            <h1 style={{
                fontSize: '24px',
                fontWeight: '600',
                marginBottom: '8px',
                color: 'var(--text-primary)'
            }}>
                Upload Dataset
            </h1>
            <p style={{
                color: 'var(--text-muted)',
                marginBottom: '32px',
                fontSize: '14px'
            }}>
                Drag and drop your CSV or Excel file to begin analysis.
            </p>

            <form
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                style={{
                    border: `2px dashed ${dragActive ? 'var(--accent)' : 'var(--border-color)'}`,
                    borderRadius: '2px',
                    padding: '48px',
                    textAlign: 'center',
                    background: dragActive ? 'rgba(249, 115, 22, 0.05)' : 'var(--bg-secondary)',
                    transition: 'all 0.2s',
                    cursor: uploading ? 'wait' : 'pointer'
                }}
            >
                <input
                    type="file"
                    id="file-upload"
                    style={{ display: 'none' }}
                    onChange={handleChange}
                    accept=".csv,.xlsx,.xls"
                    disabled={uploading}
                />

                {uploading ? (
                    <div>
                        <div style={{
                            width: '48px',
                            height: '48px',
                            margin: '0 auto 16px',
                            border: '3px solid var(--border-color)',
                            borderTopColor: 'var(--accent)',
                            borderRadius: '50%',
                            animation: 'spin 1s linear infinite'
                        }} />
                        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                            Processing {fileName}...
                        </p>
                    </div>
                ) : (
                    <>
                        <div style={{
                            width: '48px',
                            height: '48px',
                            margin: '0 auto 16px',
                            background: 'var(--bg-tertiary)',
                            borderRadius: '2px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '24px'
                        }}>📄</div>
                        <p style={{ color: 'var(--text-primary)', marginBottom: '8px', fontSize: '15px' }}>
                            Drop your file here
                        </p>
                        <p style={{ color: 'var(--text-muted)', marginBottom: '16px', fontSize: '13px' }}>
                            or click to browse
                        </p>
                        <label
                            htmlFor="file-upload"
                            className="btn-primary"
                            style={{ display: 'inline-block', cursor: 'pointer' }}
                        >
                            Select File
                        </label>
                        <p style={{
                            marginTop: '16px',
                            color: 'var(--text-muted)',
                            fontSize: '12px'
                        }}>
                            Supported: CSV, XLSX, XLS
                        </p>
                    </>
                )}
            </form>

            {error && (
                <div
                    className="bg-error animate-slideUp"
                    style={{
                        marginTop: '16px',
                        padding: '12px 16px',
                        borderRadius: '2px',
                        fontSize: '14px',
                        color: 'var(--error)'
                    }}
                >
                    <strong>Error:</strong> {error}
                </div>
            )}
        </div>
    );
}
