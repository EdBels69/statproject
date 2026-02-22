import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getDatasets, deleteDataset } from '../../lib/api';
import {
    PlusIcon,
    TrashIcon,
    PlayIcon,
    DocumentIcon,
    TableCellsIcon
} from '@heroicons/react/24/outline';

const formatBytes = (bytes) => {
    if (!bytes) return '-';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

export default function DatasetList() {
    const navigate = useNavigate();
    const [datasets, setDatasets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedId, setSelectedId] = useState(null);

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

    const handleDelete = async () => {
        if (!selectedId) return;
        const ds = datasets.find(d => d.id === selectedId);
        if (!confirm(`Удалить файл "${ds?.filename}"?`)) return;

        try {
            await deleteDataset(selectedId);
            setSelectedId(null);
            await loadDatasets();
        } catch (err) {
            alert('Ошибка удаления: ' + err.message);
        }
    };

    const handleStartAnalysis = () => {
        if (!selectedId) return;
        navigate('/copilot', { state: { datasetId: selectedId } });
    };

    if (loading) return <div className="p-8 text-center text-gray-500">Загрузка данных...</div>;

    return (
        <div className="max-w-6xl mx-auto h-[calc(100vh-100px)] flex flex-col p-6">
            {/* Header / Toolbar */}
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        📂 Менеджер Данных
                    </h1>
                    <p className="text-sm text-gray-500 mt-1">
                        Управляйте вашими наборами данных для анализа
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    {selectedId && (
                        <>
                            <button
                                onClick={handleDelete}
                                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition"
                            >
                                <TrashIcon className="w-4 h-4" />
                                Удалить
                            </button>
                            <div className="w-px h-8 bg-gray-200 mx-2"></div>
                        </>
                    )}

                    {selectedId ? (
                        <button
                            onClick={handleStartAnalysis}
                            className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition animate-pulse-slow"
                        >
                            <PlayIcon className="w-4 h-4" />
                            Приступить к анализу
                        </button>
                    ) : (
                        <button
                            disabled
                            className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-gray-400 bg-gray-100 rounded-lg cursor-not-allowed"
                        >
                            <PlayIcon className="w-4 h-4" />
                            Приступить к анализу
                        </button>
                    )}

                    <Link
                        to="/upload"
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg transition"
                    >
                        <PlusIcon className="w-4 h-4" />
                        Загрузить
                    </Link>
                </div>
            </div>

            {error && (
                <div className="bg-red-50 text-red-800 p-4 rounded-lg mb-6 border border-red-200 flex items-center gap-3">
                    <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
                    <div>
                        <span className="font-semibold block">Ошибка доступа к данным</span>
                        <span className="text-sm opacity-90">{error === "Не удалось подключиться к серверу" ? "Модуль обработки данных недоступен. Попробуйте обновить страницу." : error}</span>
                    </div>
                </div>
            )}

            {/* Data Grid */}
            <div className="bg-white border border-gray-200 rounded-lg shadow-sm flex-1 overflow-hidden flex flex-col">
                <div className="overflow-auto flex-1">
                    <table className="w-full text-left text-sm">
                        <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
                            <tr>
                                <th className="w-12 px-4 py-3 text-center">
                                    <span className="sr-only">Select</span>
                                </th>
                                <th className="px-4 py-3 font-semibold text-gray-600">Имя файла</th>
                                <th className="px-4 py-3 font-semibold text-gray-600">ID</th>
                                <th className="px-4 py-3 font-semibold text-gray-600 w-24">Формат</th>
                                <th className="px-4 py-3 font-semibold text-gray-600 text-right">Строк</th>
                                <th className="px-4 py-3 font-semibold text-gray-600 text-right">Колонок</th>
                                <th className="px-4 py-3 font-semibold text-gray-600 text-right">Размер</th>
                                <th className="px-4 py-3 font-semibold text-gray-600 text-right">Дата</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {datasets.length === 0 ? (
                                <tr>
                                    <td colSpan="8" className="px-4 py-12 text-center text-gray-500">
                                        <DocumentIcon className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                                        <p>Нет загруженных файлов</p>
                                        <Link to="/upload" className="text-blue-600 hover:underline mt-2 inline-block">
                                            Загрузить первый файл
                                        </Link>
                                    </td>
                                </tr>
                            ) : (
                                datasets.map((ds) => (
                                    <tr
                                        key={ds.id}
                                        onClick={() => setSelectedId(ds.id === selectedId ? null : ds.id)}
                                        className={`cursor-pointer transition-colors ${ds.id === selectedId ? 'bg-blue-50' : 'hover:bg-gray-50'
                                            }`}
                                    >
                                        <td className="px-4 py-3 text-center">
                                            <div className={`w-5 h-5 rounded border flex items-center justify-center mx-auto transition-colors ${ds.id === selectedId
                                                ? 'bg-blue-600 border-blue-600 text-white'
                                                : 'border-gray-300 bg-white'
                                                }`}>
                                                {ds.id === selectedId && (
                                                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                                    </svg>
                                                )}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 font-medium text-gray-900">
                                            <div className="flex items-center gap-2">
                                                <TableCellsIcon className="w-4 h-4 text-gray-400" />
                                                {ds.filename}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-gray-400 font-mono text-xs max-w-[100px] truncate" title={ds.id}>
                                            {ds.id.split('-')[0]}...
                                        </td>
                                        <td className="px-4 py-3 text-gray-500">
                                            <span className="uppercase text-xs font-bold bg-gray-100 px-2 py-0.5 rounded text-gray-600">
                                                {ds.filename.split('.').pop() || 'CSV'}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-right font-mono text-gray-600">
                                            {ds.row_count?.toLocaleString() || '-'}
                                        </td>
                                        <td className="px-4 py-3 text-right font-mono text-gray-600">
                                            {ds.col_count || '-'}
                                        </td>
                                        <td className="px-4 py-3 text-right font-mono text-gray-600">
                                            {formatBytes(ds.size)}
                                        </td>
                                        <td className="px-4 py-3 text-right text-gray-500 text-xs">
                                            {ds.created_at ? new Date(ds.created_at).toLocaleDateString() : '-'}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-500 flex justify-between">
                    <span>Всего файлов: {datasets.length}</span>
                    <span>Выберите файл чтобы активировать кнопки</span>
                </div>
            </div>
        </div>
    );
}
