import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadDataset } from '../../lib/api';
import ResearchFlowNav from '../components/ResearchFlowNav';
import {
    CloudArrowUpIcon,
    ArrowPathIcon,
    DocumentCheckIcon,
    ExclamationTriangleIcon
} from '@heroicons/react/24/outline';

const STEPS = [
    { id: 1, label: 'Чтение файла...' },
    { id: 2, label: 'Анализ структуры данных...' },
    { id: 3, label: 'Очистка и проверка...' },
    { id: 4, label: 'Технический аудит...' },
    { id: 5, label: 'Готово!' }
];

export default function Upload() {
    const navigate = useNavigate();
    const [dragActive, setDragActive] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [progressStep, setProgressStep] = useState(0);
    const [error, setError] = useState(null);
    const [fileName, setFileName] = useState(null);
    const timerRef = useRef(null);

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

    const startProgressSimulation = () => {
        setProgressStep(1);
        let step = 1;
        timerRef.current = setInterval(() => {
            step++;
            if (step < 5) { // Don't go to "Done" until actually done
                setProgressStep(step);
            }
        }, 3000); // Change text every 3 seconds
    };

    const stopProgress = () => {
        if (timerRef.current) clearInterval(timerRef.current);
    };

    useEffect(() => {
        return () => stopProgress();
    }, []);

    const handleUpload = async (file) => {
        setUploading(true);
        setError(null);
        setFileName(file.name);
        startProgressSimulation();

        // Check file size immediately
        if (file.size > 50 * 1024 * 1024) {
            setError("Файл слишком большой. Максимальный размер: 50 МБ");
            setUploading(false);
            stopProgress();
            return;
        }

        try {
            const data = await uploadDataset(file);
            setProgressStep(5);
            // Small delay to show "Done"
            setTimeout(() => {
                navigate(`/copilot`, {
                    state: {
                        datasetId: data.id,
                        newUpload: true
                    }
                });
            }, 800);
        } catch (err) {
            setError(err.message);
            stopProgress();
        } finally {
            if (!error) {
                // don't set uploading false immediately if successful to allow redirect
            } else {
                setUploading(false);
                setProgressStep(0);
            }
        }
    };

    return (
        <div className="max-w-2xl mx-auto p-6 animate-fadeIn">
            {/* Header */}
            <div className="mb-8 text-center">
                <h1 className="text-2xl font-bold text-gray-900 mb-2">
                    Загрузить данные
                </h1>
                <p className="text-gray-500">
                    Поддерживаются Excel (.xlsx, .xls) и CSV файлы до 50 МБ
                </p>
            </div>

            <div
                className={`
                    relative border-2 border-dashed rounded-xl p-12 text-center transition-all duration-200
                    ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'}
                    ${uploading ? 'pointer-events-none opacity-50' : 'hover:border-blue-400 hover:bg-gray-50'}
                `}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
            >
                <input
                    type="file"
                    id="file-upload"
                    className="hidden"
                    onChange={handleChange}
                    accept=".csv,.xlsx,.xls"
                    disabled={uploading}
                />

                {uploading ? (
                    <div className="flex flex-col items-center">
                        <div className="relative w-16 h-16 mb-4">
                            <div className="absolute inset-0 border-4 border-gray-200 rounded-full"></div>
                            <div className="absolute inset-0 border-4 border-blue-600 rounded-full border-t-transparent animate-spin"></div>
                            <DocumentCheckIcon className="absolute inset-0 w-8 h-8 m-auto text-blue-600 animate-pulse" />
                        </div>
                        <h3 className="text-lg font-semibold text-gray-900 mb-1">
                            {fileName}
                        </h3>
                        <p className="text-sm text-blue-600 font-medium mb-6 animate-pulse">
                            {STEPS.find(s => s.id === progressStep)?.label || 'Обработка...'}
                        </p>

                        {/* Steps UI */}
                        <div className="w-full max-w-xs space-y-2">
                            {STEPS.slice(0, 4).map((step) => (
                                <div key={step.id} className="flex items-center gap-3 text-xs">
                                    <div className={`w-4 h-4 rounded-full flex items-center justify-center border ${progressStep > step.id ? 'bg-green-500 border-green-500 text-white' :
                                        progressStep === step.id ? 'border-blue-500 text-blue-500' :
                                            'border-gray-300 text-gray-300'
                                        }`}>
                                        {progressStep > step.id && <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                                        {progressStep === step.id && <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce"></div>}
                                    </div>
                                    <span className={`${progressStep === step.id ? 'text-blue-700 font-medium' :
                                        progressStep > step.id ? 'text-gray-900' : 'text-gray-400'
                                        }`}>
                                        {step.label.replace('...', '')}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
                        <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mb-4 transition-transform group-hover:scale-110">
                            <CloudArrowUpIcon className="w-8 h-8" />
                        </div>
                        <span className="text-lg font-medium text-gray-900 mb-1">
                            Нажмите для выбора файла
                        </span>
                        <span className="text-sm text-gray-500 mb-6">
                            или перетащите его в эту область
                        </span>
                        <div className="px-6 py-2 bg-white border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition shadow-sm">
                            Обзор файлов
                        </div>
                    </label>
                )}
            </div>

            {error && (
                <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3 text-red-800 animate-slideUp">
                    <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <div>
                        <h4 className="font-semibold text-sm">Ошибка загрузки</h4>
                        <p className="text-sm opacity-90">{error}</p>
                    </div>
                </div>
            )}

            <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6 text-center text-sm text-gray-400">
                <div>
                    <span className="block font-semibold text-gray-600 mb-1">🔒 Безопасно</span>
                    Данные обрабатываются локально
                </div>
                <div>
                    <span className="block font-semibold text-gray-600 mb-1">⚡ Быстро</span>
                    Автоматическое определение типов
                </div>
                <div>
                    <span className="block font-semibold text-gray-600 mb-1">🧠 Умно</span>
                    AI-анализ структуры
                </div>
            </div>
        </div>
    );
}
