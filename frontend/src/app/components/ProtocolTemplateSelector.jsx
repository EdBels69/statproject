import React, { useEffect, useState } from 'react';
import { listProtocolTemplates } from '../../lib/api';

export default function ProtocolTemplateSelector({ onSelect, onCancel }) {
    const [templates, setTemplates] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        listProtocolTemplates()
            .then(setTemplates)
            .catch(err => setError(err.message))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="text-sm text-[color:var(--text-muted)] p-4">Загрузка шаблонов...</div>;
    if (error) return <div className="text-sm text-[color:var(--error)] p-4">Ошибка: {error}</div>;

    return (
        <div className="space-y-2">
            {onCancel && (
                <div className="flex justify-end px-1">
                    <button
                        onClick={onCancel}
                        className="text-xs text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors"
                        aria-label="Отмена"
                    >
                        Закрыть
                    </button>
                </div>
            )}
            {templates.length === 0 ? (
                <div className="text-sm text-[color:var(--text-muted)] italic p-4 border border-dashed border-[color:var(--border-color)] rounded-[2px] text-center">
                    Нет сохранённых шаблонов
                </div>
            ) : (
                <div className="grid gap-2 max-h-[300px] overflow-y-auto pr-2">
                    {templates.map(t => (
                        <button
                            key={t.name}
                            onClick={() => onSelect(t.name)}
                            className="text-left px-4 py-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] hover:border-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] transition-colors group w-full"
                        >
                            <div className="font-semibold text-[color:var(--text-primary)] group-hover:text-[color:var(--accent)]">
                                {t.name}
                            </div>
                            <div className="text-xs text-[color:var(--text-secondary)] mt-1 flex justify-between">
                                <span>{t.steps_count} шагов</span>
                                <span>{new Date(t.created_at).toLocaleDateString()}</span>
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
