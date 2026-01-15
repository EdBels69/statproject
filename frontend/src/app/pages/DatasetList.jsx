import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDatasets } from '../../lib/api';
import { PlusIcon, DocumentIcon, CalendarIcon } from '@heroicons/react/24/outline';
import ResearchFlowNav from '../components/ResearchFlowNav';

export default function DatasetList() {
    const [datasets, setDatasets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        loadDatasets();
    }, []);

    const loadDatasets = async () => {
        try {
            const data = await getDatasets();
            setDatasets(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading datasets...</div>;

    return (
        <div style={{ padding: '24px' }} className="animate-fadeIn">
            <ResearchFlowNav active="data" className="mb-6" />
            <div style={{
                display: 'flex',
                alignItems: 'flex-end',
                justifyContent: 'space-between',
                gap: '16px',
                marginBottom: '18px',
                paddingBottom: '14px',
                borderBottom: '1px solid var(--border-color)'
            }}>
                <div>
                    <div className="label" style={{ color: 'var(--text-muted)' }}>DATA</div>
                    <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>Datasets</h1>
                    <div style={{ marginTop: '6px', fontSize: '13px', color: 'var(--text-secondary)' }}>Upload once. Reuse forever.</div>
                </div>
                <Link to="/upload" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
                    <PlusIcon className="w-5 h-5" />
                    Upload
                </Link>
            </div>

            {datasets.length === 0 && (
                <section className="card" style={{ padding: '18px', marginBottom: '18px' }}>
                    <div className="label" style={{ color: 'var(--text-muted)' }}>Quick start</div>
                    <div style={{ marginTop: '8px', fontSize: '14px', color: 'var(--text-secondary)' }}>
                        Three steps. Zero noise.
                    </div>
                    <div style={{ marginTop: '14px', display: 'grid', gap: '10px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '32px 1fr', gap: '12px', alignItems: 'start' }}>
                            <div style={{
                                width: '32px',
                                height: '32px',
                                borderRadius: '2px',
                                border: '1px solid var(--border-color)',
                                background: 'var(--white)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 800,
                                color: 'var(--text-primary)'
                            }}>01</div>
                            <div>
                                <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>Upload</div>
                                <div style={{ marginTop: '4px', fontSize: '13px', color: 'var(--text-secondary)' }}>CSV/XLSX goes in. Columns come out.</div>
                            </div>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '32px 1fr', gap: '12px', alignItems: 'start' }}>
                            <div style={{
                                width: '32px',
                                height: '32px',
                                borderRadius: '2px',
                                border: '1px solid var(--border-color)',
                                background: 'var(--white)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 800,
                                color: 'var(--text-primary)'
                            }}>02</div>
                            <div>
                                <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>Design</div>
                                <div style={{ marginTop: '4px', fontSize: '13px', color: 'var(--text-secondary)' }}>Pick targets and groups. Build a protocol.</div>
                            </div>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '32px 1fr', gap: '12px', alignItems: 'start' }}>
                            <div style={{
                                width: '32px',
                                height: '32px',
                                borderRadius: '2px',
                                border: '1px solid var(--border-color)',
                                background: 'var(--white)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 800,
                                color: 'var(--text-primary)'
                            }}>03</div>
                            <div>
                                <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>Report</div>
                                <div style={{ marginTop: '4px', fontSize: '13px', color: 'var(--text-secondary)' }}>Read conclusions. Export PDF/DOCX.</div>
                            </div>
                        </div>
                    </div>
                    <div style={{ marginTop: '14px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                        <Link to="/upload" className="btn-primary" style={{ textDecoration: 'none' }}>Upload now</Link>
                        <Link to="/design" className="btn-secondary" style={{ textDecoration: 'none' }}>Go to design</Link>
                    </div>
                </section>
            )}

            {error && (
                <div className="card" style={{ padding: '12px 14px', marginBottom: '18px', borderColor: 'var(--black)', background: 'var(--white)', color: 'var(--text-primary)' }}>
                    <div className="label" style={{ color: 'var(--accent)' }}>Error</div>
                    <div style={{ marginTop: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>{error}</div>
                </div>
            )}

            {datasets.length === 0 ? (
                <div style={{
                    textAlign: 'center',
                    padding: '56px 16px',
                    border: '1px dashed var(--border-color)',
                    borderRadius: '2px',
                    background: 'var(--white)'
                }}>
                    <DocumentIcon className="w-12 h-12" style={{ margin: '0 auto 12px', color: 'var(--text-muted)' }} />
                    <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>No datasets</div>
                    <div style={{ marginTop: '6px', fontSize: '13px', color: 'var(--text-secondary)' }}>Upload your first file to start.</div>
                    <div style={{ marginTop: '16px' }}>
                        <Link to="/upload" className="btn-primary" style={{ textDecoration: 'none' }}>Upload a file</Link>
                    </div>
                </div>
            ) : (
                <section className="card" style={{ overflow: 'hidden' }}>
                    <table style={{ fontSize: '13px' }}>
                        <thead>
                            <tr>
                                <th>Filename</th>
                                <th>ID</th>
                                <th>Uploaded</th>
                                <th style={{ textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {datasets.map((ds) => (
                                <tr key={ds.id}>
                                    <td style={{ display: 'flex', alignItems: 'center', gap: '10px', fontWeight: 600, color: 'var(--text-primary)' }}>
                                        <span style={{
                                            width: '28px',
                                            height: '28px',
                                            borderRadius: '2px',
                                            border: '1px solid var(--border-color)',
                                            display: 'inline-flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            background: 'var(--white)'
                                        }}>
                                            <DocumentIcon className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                                        </span>
                                        <span>{ds.filename}</span>
                                    </td>
                                    <td style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{ds.id.substring(0, 8)}...</td>
                                    <td style={{ color: 'var(--text-secondary)' }}>
                                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                                            <CalendarIcon className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                                            Today
                                        </span>
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                        <div style={{ display: 'inline-flex', gap: '12px' }}>
                                            <Link to={`/profile/${ds.id}`} style={{ color: 'var(--text-secondary)', fontWeight: 600, textDecoration: 'none' }}>Profile</Link>
                                            <Link to={`/design/${ds.id}`} style={{ color: 'var(--text-primary)', fontWeight: 700, textDecoration: 'none' }}>Design</Link>
                                            <Link to={`/analyze/${ds.id}`} style={{ color: 'var(--accent)', fontWeight: 800, textDecoration: 'none' }}>Analyze</Link>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </section>
            )}
        </div>
    );
}
