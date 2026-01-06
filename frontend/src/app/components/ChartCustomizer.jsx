import React, { useState } from 'react';
import { AdjustmentsHorizontalIcon, XMarkIcon } from '@heroicons/react/24/outline';

const ChartCustomizer = ({ runId, stepId, datasetId, currentImage, onUpdate }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [loading, setLoading] = useState(false);

    // Form State
    const [params, setParams] = useState({
        title: '',
        xlabel: '',
        ylabel: '',
        theme: 'default',
        color: '#4F46E5' // Indigo-600
    });

    const handleOpen = () => {
        setIsOpen(true);
        // Reset or load existing? For simplicity, start blank or default
    };

    const handleUpdate = async () => {
        setLoading(true);
        try {
            const res = await fetch(`http://localhost:8000/api/v1/analysis/run/${runId}/step/${stepId}/plot?dataset_id=${datasetId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            });

            if (!res.ok) throw new Error('Update failed');

            const data = await res.json();
            if (data.plot_image) {
                onUpdate(data.plot_image); // Callback to parent to update image
                setIsOpen(false);
            }
        } catch (err) {
            console.error(err);
            alert('Не удалось обновить график');
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <button
                onClick={handleOpen}
                className="absolute top-2 right-2 p-2 bg-white/80 hover:bg-white rounded-full shadow border text-gray-500 hover:text-blue-600 transition-colors"
                title="Настроить график"
            >
                <AdjustmentsHorizontalIcon className="w-5 h-5" />
            </button>

            {isOpen && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 relative animate-fadeIn">
                        <button
                            onClick={() => setIsOpen(false)}
                            className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
                        >
                            <XMarkIcon className="w-6 h-6" />
                        </button>

                        <h3 className="text-lg font-bold text-gray-900 mb-4">Настройка Графика</h3>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Заголовок</label>
                                <input
                                    type="text"
                                    className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                                    value={params.title}
                                    onChange={e => setParams({ ...params, title: e.target.value })}
                                    placeholder="Название графика"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Ось X</label>
                                    <input
                                        type="text"
                                        className="w-full border rounded-lg px-3 py-2 text-sm"
                                        value={params.xlabel}
                                        onChange={e => setParams({ ...params, xlabel: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Ось Y</label>
                                    <input
                                        type="text"
                                        className="w-full border rounded-lg px-3 py-2 text-sm"
                                        value={params.ylabel}
                                        onChange={e => setParams({ ...params, ylabel: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Тема</label>
                                    <select
                                        className="w-full border rounded-lg px-3 py-2 text-sm"
                                        value={params.theme}
                                        onChange={e => setParams({ ...params, theme: e.target.value })}
                                    >
                                        <option value="default">Standard</option>
                                        <option value="seaborn">Scientific (Seaborn)</option>
                                        <option value="ggplot">Grid (ggplot)</option>
                                        <option value="dark">Dark Mode</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Цвет (Основной)</label>
                                    <input
                                        type="color"
                                        className="w-full h-9 border rounded-lg cursor-pointer"
                                        value={params.color}
                                        onChange={e => setParams({ ...params, color: e.target.value })}
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="mt-6 flex justify-end gap-3">
                            <button
                                onClick={() => setIsOpen(false)}
                                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm font-medium"
                            >
                                Отмена
                            </button>
                            <button
                                onClick={handleUpdate}
                                disabled={loading}
                                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                            >
                                {loading ? 'Обновление...' : 'Применить'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default ChartCustomizer;
