/**
 * WranglingPanel — панель data wrangling трансформаций.
 *
 * Операции:
 *  - split_column  : разбить значения по разделителю → строки / новые колонки
 *  - recode_values : маппинг старых значений в новые
 *  - derive_column : вычислить новую колонку по формуле
 *  - bin_variable  : разбить числовую переменную на группы
 *  - string_clean  : trim / lowercase / uppercase / replace
 */
import React, { useState, useMemo } from 'react';
import { modifyDataset } from '@/lib/api';

// ── Стили-константы (совпадают с дизайн-системой проекта) ─────────────────────
const cls = {
    btn:    'px-3 py-1.5 rounded-[2px] text-xs font-semibold border transition-colors',
    btnPri: 'bg-[color:var(--accent)] text-white border-[color:var(--accent)] hover:bg-[color:var(--accent-hover)]',
    btnSec: 'bg-[color:var(--white)] text-[color:var(--text-primary)] border-[color:var(--border-color)] hover:bg-[color:var(--bg-secondary)]',
    input:  'w-full px-2.5 py-1.5 text-sm rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-primary)] outline-none focus:border-[color:var(--accent)]',
    select: 'w-full px-2.5 py-1.5 text-sm rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-primary)] outline-none',
    label:  'block text-xs font-semibold text-[color:var(--text-secondary)] mb-1',
    field:  'space-y-1',
    row:    'flex items-center gap-3',
    error:  'text-xs text-red-600 mt-1',
    chip:   'inline-block px-1.5 py-0.5 text-[11px] rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] cursor-pointer hover:bg-[color:var(--accent)] hover:text-white hover:border-[color:var(--accent)] transition-colors',
};

// ── Список операций ────────────────────────────────────────────────────────────
const OPERATIONS = [
    { id: 'split_column',  label: 'Разбить колонку' },
    { id: 'recode_values', label: 'Рекодировать'     },
    { id: 'derive_column', label: 'Вычислить колонку'},
    { id: 'bin_variable',  label: 'Разбить на группы'},
    { id: 'string_clean',  label: 'Очистить текст'  },
];

// ── Helpers ────────────────────────────────────────────────────────────────────
const ColSelect = ({ value, onChange, columns, label, placeholder = 'Выбери колонку...' }) => (
    <div className={cls.field}>
        {label && <label className={cls.label}>{label}</label>}
        <select className={cls.select} value={value} onChange={e => onChange(e.target.value)}>
            <option value="">{placeholder}</option>
            {columns.map(c => <option key={c.name || c} value={c.name || c}>{c.name || c}</option>)}
        </select>
    </div>
);

// Достаём уникальные значения колонки из head-строк профиля (до 50)
function uniqueVals(profile, col) {
    if (!profile || !col) return [];
    const rows = Array.isArray(profile.head) ? profile.head : [];
    const seen = new Set();
    rows.forEach(r => {
        const v = r[col];
        if (v !== null && v !== undefined) seen.add(String(v));
    });
    return [...seen].slice(0, 50).sort();
}

// ── Форма: split_column ────────────────────────────────────────────────────────
const SplitForm = ({ columns, onApply, applying }) => {
    const [col, setCol] = useState('');
    const [sep, setSep] = useState(',');
    const [mode, setMode] = useState('rows');
    const [prefix, setPrefix] = useState('');
    const [trim, setTrim] = useState(true);
    const [err, setErr] = useState('');

    const apply = async () => {
        if (!col) return setErr('Выбери колонку');
        if (!sep) return setErr('Укажи разделитель');
        setErr('');
        await onApply([{
            type: 'split_column', column: col,
            config: { separator: sep, mode, trim, prefix: prefix || `${col}_` },
        }]);
    };

    return (
        <div className="space-y-3">
            <ColSelect value={col} onChange={setCol} columns={columns} label="Колонка" />
            <div className={cls.field}>
                <label className={cls.label}>Разделитель</label>
                <input className={cls.input} value={sep} onChange={e => setSep(e.target.value)} placeholder="например , или ;" />
            </div>
            <div className={cls.field}>
                <label className={cls.label}>Режим</label>
                <div className={cls.row}>
                    {[['rows', 'В строки (long)'], ['columns', 'В колонки (wide)']].map(([v, l]) => (
                        <label key={v} className="flex items-center gap-1.5 text-sm cursor-pointer">
                            <input type="radio" value={v} checked={mode === v} onChange={() => setMode(v)} />
                            {l}
                        </label>
                    ))}
                </div>
            </div>
            {mode === 'columns' && (
                <div className={cls.field}>
                    <label className={cls.label}>Префикс новых колонок</label>
                    <input className={cls.input} value={prefix} onChange={e => setPrefix(e.target.value)} placeholder={`${col || 'col'}_`} />
                </div>
            )}
            <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={trim} onChange={e => setTrim(e.target.checked)} />
                Убрать пробелы вокруг значений
            </label>
            {err && <div className={cls.error}>{err}</div>}
            <button className={`${cls.btn} ${cls.btnPri}`} disabled={applying} onClick={apply}>
                {applying ? 'Применяю...' : 'Применить'}
            </button>
        </div>
    );
};

// ── Форма: recode_values ───────────────────────────────────────────────────────
const RecodeForm = ({ columns, profile, onApply, applying }) => {
    const [col, setCol] = useState('');
    const [rows, setRows] = useState([{ from: '', to: '' }]);
    const [unmapped, setUnmapped] = useState('keep');
    const [err, setErr] = useState('');

    const handleColChange = (c) => {
        setCol(c);
        const vals = uniqueVals(profile, c);
        setRows(vals.length > 0 ? vals.map(v => ({ from: v, to: '' })) : [{ from: '', to: '' }]);
    };

    const setRow = (idx, field, val) => {
        setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: val } : r));
    };

    const apply = async () => {
        if (!col) return setErr('Выбери колонку');
        const mapping = {};
        rows.forEach(r => { if (r.from && r.to) mapping[r.from] = r.to; });
        if (Object.keys(mapping).length === 0) return setErr('Заполни хотя бы одно соответствие');
        setErr('');
        await onApply([{ type: 'recode_values', column: col, config: { mapping, unmapped } }]);
    };

    return (
        <div className="space-y-3">
            <ColSelect value={col} onChange={handleColChange} columns={columns} label="Колонка" />
            {col && (
                <div className={cls.field}>
                    <label className={cls.label}>Маппинг значений</label>
                    <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                        {rows.map((r, i) => (
                            <div key={i} className={cls.row}>
                                <input className={cls.input} placeholder="Старое" value={r.from}
                                    onChange={e => setRow(i, 'from', e.target.value)} />
                                <span className="text-[color:var(--text-muted)] shrink-0">→</span>
                                <input className={cls.input} placeholder="Новое" value={r.to}
                                    onChange={e => setRow(i, 'to', e.target.value)} />
                            </div>
                        ))}
                    </div>
                    <button className={`mt-1 ${cls.btn} ${cls.btnSec} text-[11px]`}
                        onClick={() => setRows(p => [...p, { from: '', to: '' }])}>
                        + Добавить строку
                    </button>
                </div>
            )}
            <div className={cls.field}>
                <label className={cls.label}>Нерекодированные значения</label>
                <div className={cls.row}>
                    {[['keep', 'Оставить'], ['null', 'Сделать пустыми']].map(([v, l]) => (
                        <label key={v} className="flex items-center gap-1.5 text-sm cursor-pointer">
                            <input type="radio" value={v} checked={unmapped === v} onChange={() => setUnmapped(v)} />
                            {l}
                        </label>
                    ))}
                </div>
            </div>
            {err && <div className={cls.error}>{err}</div>}
            <button className={`${cls.btn} ${cls.btnPri}`} disabled={applying} onClick={apply}>
                {applying ? 'Применяю...' : 'Применить'}
            </button>
        </div>
    );
};

// ── Форма: derive_column ───────────────────────────────────────────────────────
const TEMPLATES = [
    { label: 'ИМТ',          formula: 'weight / (height / 100) ** 2', name: 'BMI'   },
    { label: 'Дельта',       formula: 'post - pre',                    name: 'delta' },
    { label: '% от базового',formula: '(post / pre - 1) * 100',       name: 'pct'   },
];

const DeriveForm = ({ columns, onApply, applying }) => {
    const [newCol, setNewCol] = useState('');
    const [formula, setFormula] = useState('');
    const [err, setErr] = useState('');

    const insertCol = (name) => {
        setFormula(prev => prev ? `${prev} ${name}` : name);
    };

    const useTemplate = (t) => {
        setFormula(t.formula);
        if (!newCol) setNewCol(t.name);
    };

    const apply = async () => {
        if (!newCol.trim()) return setErr('Укажи имя новой колонки');
        if (!formula.trim()) return setErr('Укажи формулу');
        setErr('');
        // Extract only column names that actually appear in the formula
        const allNames = columns.map(c => c.name || c);
        const usedCols = allNames.filter(name => formula.includes(name));
        await onApply([{
            type: 'derive_column', column: newCol.trim(),
            config: { formula: formula.trim(), source_columns: usedCols },
        }]);
    };

    return (
        <div className="space-y-3">
            <div className={cls.field}>
                <label className={cls.label}>Имя новой колонки</label>
                <input className={cls.input} value={newCol} onChange={e => setNewCol(e.target.value)} placeholder="например BMI" />
            </div>
            <div className={cls.field}>
                <label className={cls.label}>Формула</label>
                <input className={cls.input} value={formula} onChange={e => setFormula(e.target.value)}
                    placeholder="например weight / (height / 100) ** 2" />
                <div className="text-[11px] text-[color:var(--text-muted)] mt-1">
                    Используй имена колонок, +  -  *  /  **  ( )
                </div>
            </div>
            <div className={cls.field}>
                <label className={cls.label}>Шаблоны</label>
                <div className="flex flex-wrap gap-1.5">
                    {TEMPLATES.map(t => (
                        <button key={t.label} className={`${cls.btn} ${cls.btnSec}`} onClick={() => useTemplate(t)}>
                            {t.label}
                        </button>
                    ))}
                </div>
            </div>
            <div className={cls.field}>
                <label className={cls.label}>Доступные колонки</label>
                <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                    {columns.map(c => (
                        <span key={c.name || c} className={cls.chip} onClick={() => insertCol(c.name || c)}>
                            {c.name || c}
                        </span>
                    ))}
                </div>
            </div>
            {err && <div className={cls.error}>{err}</div>}
            <button className={`${cls.btn} ${cls.btnPri}`} disabled={applying} onClick={apply}>
                {applying ? 'Применяю...' : 'Применить'}
            </button>
        </div>
    );
};

// ── Форма: bin_variable ────────────────────────────────────────────────────────
const BinForm = ({ columns, onApply, applying }) => {
    const numericCols = useMemo(() =>
        columns.filter(c => {
            const t = (c.uiType || c.type || '').toLowerCase();
            return t === 'numeric' || t === 'integer' || t === 'float' || t.startsWith('int') || t.startsWith('float');
        }), [columns]);

    const [col, setCol] = useState('');
    const [newCol, setNewCol] = useState('');
    const [method, setMethod] = useState('equal_width');
    const [nBins, setNBins] = useState(4);
    const [binsStr, setBinsStr] = useState('');
    const [labelsStr, setLabelsStr] = useState('');
    const [err, setErr] = useState('');

    const apply = async () => {
        if (!col) return setErr('Выбери колонку');
        const cfg = {
            new_column: newCol || `${col}_bin`,
            method,
            n_bins: Number(nBins),
        };
        if (method === 'custom') {
            const bins = binsStr.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
            if (bins.length < 2) return setErr('Укажи минимум 2 границы через запятую');
            cfg.bins = bins;
        }
        if (labelsStr.trim()) {
            cfg.labels = labelsStr.split(',').map(s => s.trim()).filter(Boolean);
        }
        setErr('');
        await onApply([{ type: 'bin_variable', column: col, config: cfg }]);
    };

    return (
        <div className="space-y-3">
            <ColSelect value={col} onChange={v => { setCol(v); setNewCol(''); }}
                columns={numericCols.length > 0 ? numericCols : columns}
                label="Числовая колонка" />
            <div className={cls.field}>
                <label className={cls.label}>Имя новой колонки (необязательно)</label>
                <input className={cls.input} value={newCol} onChange={e => setNewCol(e.target.value)}
                    placeholder={col ? `${col}_bin` : 'имя_bin'} />
            </div>
            <div className={cls.field}>
                <label className={cls.label}>Метод разбивки</label>
                <div className="flex flex-wrap gap-3">
                    {[['equal_width','Равные интервалы'],['quantile','По квантилям'],['custom','Свои границы']].map(([v, l]) => (
                        <label key={v} className="flex items-center gap-1.5 text-sm cursor-pointer">
                            <input type="radio" value={v} checked={method === v} onChange={() => setMethod(v)} />
                            {l}
                        </label>
                    ))}
                </div>
            </div>
            {method === 'custom' ? (
                <div className={cls.field}>
                    <label className={cls.label}>Границы через запятую</label>
                    <input className={cls.input} value={binsStr} onChange={e => setBinsStr(e.target.value)}
                        placeholder="0, 30, 50, 70, 120" />
                </div>
            ) : (
                <div className={cls.field}>
                    <label className={cls.label}>Количество групп</label>
                    <input className={cls.input} type="number" min={2} max={20} value={nBins}
                        onChange={e => setNBins(e.target.value)} />
                </div>
            )}
            <div className={cls.field}>
                <label className={cls.label}>Подписи групп через запятую (необязательно)</label>
                <input className={cls.input} value={labelsStr} onChange={e => setLabelsStr(e.target.value)}
                    placeholder="&lt;30, 30-50, 50-70, 70+" />
            </div>
            {err && <div className={cls.error}>{err}</div>}
            <button className={`${cls.btn} ${cls.btnPri}`} disabled={applying} onClick={apply}>
                {applying ? 'Применяю...' : 'Применить'}
            </button>
        </div>
    );
};

// ── Форма: string_clean ────────────────────────────────────────────────────────
const StringCleanForm = ({ columns, onApply, applying }) => {
    const [col, setCol] = useState('');
    const [ops, setOps] = useState({ trim: true, lowercase: false, uppercase: false, replace: false });
    const [from, setFrom] = useState('');
    const [to, setTo] = useState('');
    const [err, setErr] = useState('');

    const toggleOp = (op) => setOps(prev => ({ ...prev, [op]: !prev[op] }));

    const apply = async () => {
        if (!col) return setErr('Выбери колонку');
        const operations = Object.entries(ops).filter(([, v]) => v).map(([k]) => k);
        if (operations.length === 0) return setErr('Выбери хотя бы одну операцию');
        if (ops.replace && !from) return setErr('Укажи что заменить');
        setErr('');
        await onApply([{
            type: 'string_clean', column: col,
            config: { operations, replace_from: from, replace_to: to },
        }]);
    };

    return (
        <div className="space-y-3">
            <ColSelect value={col} onChange={setCol} columns={columns} label="Колонка" />
            <div className={cls.field}>
                <label className={cls.label}>Операции</label>
                <div className="space-y-1.5">
                    {[
                        ['trim',      'Убрать пробелы по краям'],
                        ['lowercase', 'В нижний регистр'],
                        ['uppercase', 'В ВЕРХНИЙ регистр'],
                        ['replace',   'Заменить текст'],
                    ].map(([k, l]) => (
                        <label key={k} className="flex items-center gap-2 text-sm cursor-pointer">
                            <input type="checkbox" checked={ops[k]} onChange={() => toggleOp(k)} />
                            {l}
                        </label>
                    ))}
                </div>
            </div>
            {ops.replace && (
                <div className="space-y-2 pl-3 border-l-2 border-[color:var(--border-color)]">
                    <div className={cls.field}>
                        <label className={cls.label}>Заменить</label>
                        <input className={cls.input} value={from} onChange={e => setFrom(e.target.value)} placeholder="н/д" />
                    </div>
                    <div className={cls.field}>
                        <label className={cls.label}>На</label>
                        <input className={cls.input} value={to} onChange={e => setTo(e.target.value)} placeholder="(оставь пустым = удалить)" />
                    </div>
                </div>
            )}
            {err && <div className={cls.error}>{err}</div>}
            <button className={`${cls.btn} ${cls.btnPri}`} disabled={applying} onClick={apply}>
                {applying ? 'Применяю...' : 'Применить'}
            </button>
        </div>
    );
};

// ── Главный компонент ──────────────────────────────────────────────────────────
const FORMS = {
    split_column:  SplitForm,
    recode_values: RecodeForm,
    derive_column: DeriveForm,
    bin_variable:  BinForm,
    string_clean:  StringCleanForm,
};

/**
 * Props:
 *   datasetId  : string
 *   columns    : Array<{ name, uiType }>
 *   profile    : объект профиля (для unique values)
 *   onRefresh  : () => void  — перезагрузить профиль и scan report
 */
const WranglingPanel = ({ datasetId, columns, profile, onRefresh }) => {
    const [open, setOpen] = useState(false);
    const [activeOp, setActiveOp] = useState('split_column');
    const [applying, setApplying] = useState(false);
    const [success, setSuccess] = useState('');
    const [error, setError] = useState('');

    const handleApply = async (actions) => {
        if (!datasetId) return;
        setApplying(true);
        setSuccess('');
        setError('');
        try {
            await modifyDataset(datasetId, actions);
            await onRefresh();
            const opLabel = OPERATIONS.find(o => o.id === actions[0]?.type)?.label || '';
            setSuccess(`${opLabel} применено`);
            setTimeout(() => setSuccess(''), 3000);
        } catch (e) {
            setError(e.message || 'Ошибка при применении');
        } finally {
            setApplying(false);
        }
    };

    const ActiveForm = FORMS[activeOp];

    return (
        <div className="mb-4">
            {/* Toggle button */}
            <button
                type="button"
                onClick={() => setOpen(v => !v)}
                className="flex items-center gap-2 text-sm font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] transition-colors"
            >
                <span className="text-[color:var(--accent)]">{open ? '▲' : '▼'}</span>
                Трансформации данных
                <span className="text-[11px] font-normal text-[color:var(--text-muted)]">
                    split · recode · derive · bin · clean
                </span>
            </button>

            {open && (
                <div className="mt-3 bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px] p-4 animate-fadeIn">
                    {/* Operation tabs */}
                    <div className="flex flex-wrap gap-1.5 mb-4 pb-3 border-b border-[color:var(--border-color)]">
                        {OPERATIONS.map(op => (
                            <button
                                key={op.id}
                                onClick={() => { setActiveOp(op.id); setSuccess(''); setError(''); }}
                                className={`${cls.btn} ${activeOp === op.id ? cls.btnPri : cls.btnSec}`}
                            >
                                {op.label}
                            </button>
                        ))}
                    </div>

                    {/* Active form */}
                    {datasetId ? (
                        <ActiveForm
                            columns={columns}
                            profile={profile}
                            onApply={handleApply}
                            applying={applying}
                        />
                    ) : (
                        <div className="text-sm text-[color:var(--text-muted)]">Сначала выбери датасет</div>
                    )}

                    {/* Feedback */}
                    {success && (
                        <div className="mt-3 px-3 py-2 rounded-[2px] bg-green-50 border border-green-200 text-green-700 text-xs font-semibold">
                            {success}
                        </div>
                    )}
                    {error && (
                        <div className="mt-3 px-3 py-2 rounded-[2px] bg-red-50 border border-red-200 text-red-700 text-xs">
                            {error}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default WranglingPanel;
