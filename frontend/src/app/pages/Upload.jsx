import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadDataset } from '../../lib/api';

export default function Upload() {
    const navigate = useNavigate();
    const [dragActive, setDragActive] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);

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
        <div className="max-w-4xl mx-auto p-8">
            <h1 className="text-3xl font-bold mb-6 text-slate-800">Загрузка данных</h1>

            <form
                className={`relative p-10 border-2 border-dashed rounded-xl transition-colors
            ${dragActive ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white"}
            ${uploading ? "opacity-50 cursor-wait" : ""}`}
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

                <div className="text-center">
                    <div className="text-5xl mb-4">📁</div>
                    <p className="text-lg mb-2 text-slate-700">Перетащите файл сюда</p>
                    <p className="text-sm text-slate-500 mb-4">или</p>
                    <label
                        htmlFor="file-upload"
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer transition-colors"
                    >
                        {uploading ? "Загрузка..." : "Выбрать файл"}
                    </label>
                    <p className="mt-4 text-xs text-slate-400">Поддерживаются: CSV, Excel</p>
                </div>
            </form>

            {error && (
                <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-lg border border-red-200">
                    ❌ Ошибка: {error}
                </div>
            )}
        </div>
    );
}
