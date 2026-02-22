import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { studyApi } from '../services/studyApi';
import {
    ArrowLeftIcon,
    CheckIcon,
    PlusIcon,
    SparklesIcon,
    TrashIcon
} from '@heroicons/react/24/outline';

const StudySetup = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // Form State
    const [config, setConfig] = useState({
        title: '',
        objective: '',
        study_type: 'rct',
        hypotheses: [],
        endpoints: [],
        group_column: '',
        subject_id_column: '',
        visits: [],
        alpha: 0.05
    });

    useEffect(() => {
        const loadData = async () => {
            try {
                setLoading(true);
                try {
                    const existingConfig = await studyApi.getConfig(id);
                    setConfig(existingConfig);
                } catch {
                    console.log('No existing config, starting fresh');
                }
            } catch (err) {
                console.error('Failed to load study data', err);
            } finally {
                setLoading(false);
            }
        };

        loadData();
    }, [id]);

    const handleSave = async () => {
        try {
            setSaving(true);
            await studyApi.saveConfig(id, config);
            // Show success notification
        } catch (err) {
            console.error('Failed to save', err);
            // Show error
        } finally {
            setSaving(false);
        }
    };

    const addHypothesis = () => {
        setConfig(prev => ({
            ...prev,
            hypotheses: [...prev.hypotheses, { h0: '', h1: '', primary: false }]
        }));
    };

    const updateHypothesis = (index, field, value) => {
        const newHypotheses = [...config.hypotheses];
        newHypotheses[index] = { ...newHypotheses[index], [field]: value };
        setConfig({ ...config, hypotheses: newHypotheses });
    };

    if (loading) return <div className="p-8">Loading study configuration...</div>;

    return (
        <div className="max-w-5xl mx-auto p-6 space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                    <button onClick={() => navigate(-1)} className="p-2 hover:bg-gray-100 rounded-full">
                        <ArrowLeftIcon className="w-5 h-5" />
                    </button>
                    <h1 className="text-2xl font-bold text-gray-900">Настройка исследования</h1>
                </div>
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                    <CheckIcon className="w-4 h-4" />
                    <span>{saving ? 'Сохранение...' : 'Сохранить настройки'}</span>
                </button>
            </div>

            {/* Main Form */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                {/* Left Column: General Info */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm space-y-4">
                        <h2 className="text-lg font-semibold">Общая информация</h2>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Название исследования</label>
                            <input
                                type="text"
                                value={config.title}
                                onChange={e => setConfig({ ...config, title: e.target.value })}
                                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                                placeholder="Например: Эффективность препарата Х при лечении Y"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Цель исследования</label>
                            <textarea
                                rows={3}
                                value={config.objective}
                                onChange={e => setConfig({ ...config, objective: e.target.value })}
                                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                                placeholder="Описать основную цель..."
                            />
                        </div>
                    </div>

                    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm space-y-4">
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-semibold">Гипотезы</h2>
                            <button
                                onClick={addHypothesis}
                                className="text-sm text-blue-600 hover:text-blue-800 flex items-center"
                            >
                                <PlusIcon className="w-4 h-4 mr-1" /> Добавить
                            </button>
                        </div>

                        {config.hypotheses.length === 0 ? (
                            <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg">
                                Гипотезы не заданы. Добавьте гипотезу вручную или используйте AI.
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {config.hypotheses.map((h, idx) => (
                                    <div key={idx} className="p-4 border rounded-lg bg-gray-50 relative group">
                                        <button
                                            onClick={() => {
                                                const newH = [...config.hypotheses];
                                                newH.splice(idx, 1);
                                                setConfig({ ...config, hypotheses: newH });
                                            }}
                                            className="absolute top-2 right-2 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                                        >
                                            <TrashIcon className="w-4 h-4" />
                                        </button>

                                        <div className="grid gap-3">
                                            <div>
                                                <span className="text-xs font-bold text-gray-500">H₀ (Нулевая)</span>
                                                <input
                                                    type="text"
                                                    value={h.h0}
                                                    onChange={e => updateHypothesis(idx, 'h0', e.target.value)}
                                                    className="w-full mt-1 px-2 py-1 border rounded text-sm"
                                                    placeholder="Нет различий..."
                                                />
                                            </div>
                                            <div>
                                                <span className="text-xs font-bold text-gray-500">H₁ (Альтернативная)</span>
                                                <input
                                                    type="text"
                                                    value={h.h1}
                                                    onChange={e => updateHypothesis(idx, 'h1', e.target.value)}
                                                    className="w-full mt-1 px-2 py-1 border rounded text-sm"
                                                    placeholder="Есть различия..."
                                                />
                                            </div>
                                            <label className="flex items-center space-x-2">
                                                <input
                                                    type="checkbox"
                                                    checked={h.primary}
                                                    onChange={e => updateHypothesis(idx, 'primary', e.target.checked)}
                                                />
                                                <span className="text-sm text-gray-600">Основная гипотеза</span>
                                            </label>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Column: Configuration */}
                <div className="space-y-6">
                    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm space-y-4">
                        <h2 className="text-lg font-semibold">Параметры данных</h2>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Колонка групп</label>
                            <input
                                type="text"
                                value={config.group_column}
                                onChange={e => setConfig({ ...config, group_column: e.target.value })}
                                className="w-full px-3 py-2 border rounded-lg"
                                placeholder="Например: Group"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">ID пациента</label>
                            <input
                                type="text"
                                value={config.subject_id_column}
                                onChange={e => setConfig({ ...config, subject_id_column: e.target.value })}
                                className="w-full px-3 py-2 border rounded-lg"
                                placeholder="Например: SubjectID"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Визиты (через запятую)</label>
                            <input
                                type="text"
                                value={config.visits.join(', ')}
                                onChange={e => setConfig({ ...config, visits: e.target.value.split(',').map(s => s.trim()) })}
                                className="w-full px-3 py-2 border rounded-lg"
                                placeholder="V1, V2, V3"
                            />
                            <p className="text-xs text-gray-500 mt-1">Порядок важен для графиков</p>
                        </div>
                    </div>

                    <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                        <div className="flex items-start space-x-3">
                            <SparklesIcon className="w-5 h-5 text-blue-600 mt-0.5" />
                            <div>
                                <h3 className="text-sm font-bold text-blue-900">AI Ассистент</h3>
                                <p className="text-xs text-blue-700 mt-1">
                                    Заполните "Цель исследования", и AI предложит подходящие гипотезы и endpoints.
                                </p>
                                <button className="mt-3 text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700">
                                    Предложить гипотезы
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StudySetup;
