import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDatasets, deleteDataset, uploadPrimaryDataset } from '../../lib/api';
import { PlusIcon, DocumentIcon, CalendarIcon } from '@heroicons/react/24/outline';
import ResearchFlowNav from '../components/ResearchFlowNav';

export default function DatasetList() {
    const [datasets, setDatasets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [primaryLoading, setPrimaryLoading] = useState(false);

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

    const handleLoadPrimary = async () => {
        if (primaryLoading) return;
        setPrimaryLoading(true);
        setError(null);
        try {
            await uploadPrimaryDataset();
            await loadDatasets();
        } catch (err) {
            const message = err?.message || 'Не удалось загрузить файл данных';
            setError(message);
        } finally {
            setPrimaryLoading(false);
        }
    };

    const handleDelete = async (id, filename) => {
        if (!confirm(`Удалить файл данных "${filename}"?`)) return;
        try {
            await deleteDataset(id);
            await loadDatasets(); // Reload list
        } catch (err) {
            alert('Ошибка удаления: ' + err.message);
        }
    };

    const nextDatasetId = datasets?.[0]?.id || null;

    if (loading) return <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>Загружаю файлы данных…</div>;

    return (
        <div style={{ padding: '24px' }} className="animate-fadeIn">
            <ResearchFlowNav active="data" className="mb-6" datasetId={nextDatasetId} showMenu={false} />
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
                    <div className="label" style={{ color: 'var(--text-muted)' }}>ДАННЫЕ</div>
                    <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>Файлы данных</h1>
                    <div style={{ marginTop: '6px', fontSize: '13px', color: 'var(--text-secondary)' }}>Загрузите файл один раз и используйте его сколько угодно.</div>
                </div>
                <Link to="/upload" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
                    <PlusIcon className="w-5 h-5" />
                    Загрузить
                </Link>
            </div>

            {error && (
                <div className="card" style={{ padding: '12px 14px', marginBottom: '18px', borderColor: 'var(--black)', background: 'var(--white)', color: 'var(--text-primary)' }}>
                    <div className="label" style={{ color: 'var(--accent)' }}>Ошибка</div>
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
                    <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>Нет файлов данных</div>
                    <div style={{ marginTop: '6px', fontSize: '13px', color: 'var(--text-secondary)' }}>Загрузите первый файл, чтобы начать.</div>
                    <div style={{ marginTop: '16px', display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap' }}>
                        <Link to="/upload" className="btn-primary" style={{ textDecoration: 'none' }}>Загрузить файл</Link>
                        <button
                            type="button"
                            className="btn-secondary"
                            onClick={handleLoadPrimary}
                            disabled={primaryLoading}
                            style={{ opacity: primaryLoading ? 0.6 : 1 }}
                        >
                            {primaryLoading ? 'Загружаю «Первичку»…' : 'Загрузить «Первичку» (из docs)'}
                        </button>
                    </div>
                </div>
            ) : (
                <section className="card" style={{ overflow: 'hidden' }}>
                    <table style={{ fontSize: '13px' }}>
                        <thead>
                            <tr>
                                <th>Имя файла</th>
                                <th style={{ minWidth: '300px' }}>ID</th>
                                <th>Загружен</th>
                                <th style={{ textAlign: 'right' }}>Действия</th>
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
                                    <td className="mono" style={{ color: 'var(--text-secondary)', fontSize: '11px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }} title={ds.id}>{ds.id}</td>
                                    <td style={{ color: 'var(--text-secondary)' }}>
                                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                                            <CalendarIcon className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                                            {(ds.uploaded_at || ds.created_at) ? new Date(ds.uploaded_at || ds.created_at).toLocaleDateString('ru-RU') : 'Неизвестно'}
                                        </span>
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                        <div className="table-actions">
                                            <Link to={`/prep/${ds.id}`} className="action-chip action-chip--neutral">Переменные</Link>
                                            <Link to={`/tests/${ds.id}`} className="action-chip action-chip--neutral">Тесты</Link>
                                            <Link to={`/study-setup/${ds.id}`} className="action-chip action-chip--dark">Настройки</Link>
                                            <Link to={`/design/${ds.id}`} className="action-chip action-chip--dark">Конструктор</Link>
                                            <Link to={`/protocol?dataset=${encodeURIComponent(ds.id)}`} className="action-chip action-chip--accent">Авто‑отчёт</Link>
                                            <Link to={`/results/${ds.id}`} className="action-chip action-chip--accent">Результаты</Link>
                                            <button type="button" onClick={() => handleDelete(ds.id, ds.filename)} className="action-chip action-chip--danger">Удалить</button>
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
