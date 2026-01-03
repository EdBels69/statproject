import { useState, useEffect } from 'react';

// Minimalist Type Icons (Text-based)
const TypeIcon = ({ type }) => {
    switch (type) {
        case 'numeric': return <span className="font-mono text-[9px] text-slate-500 font-bold border border-slate-300 px-1 rounded-sm">NUM</span>;
        case 'categorical': return <span className="font-mono text-[9px] text-slate-500 font-bold border border-slate-300 px-1 rounded-sm">CAT</span>;
        case 'datetime': return <span className="font-mono text-[9px] text-slate-500 font-bold border border-slate-300 px-1 rounded-sm">DAT</span>;
        default: return <span className="font-mono text-[9px] text-slate-500 font-bold border border-slate-300 px-1 rounded-sm">TXT</span>;
    }
};

export default function VariableSelector({ allColumns, onRun, loading }) {
    const [available, setAvailable] = useState([]);
    const [targetCols, setTargetCols] = useState([]);
    const [groupCol, setGroupCol] = useState(null);

    const [selectedAvailable, setSelectedAvailable] = useState([]);
    const [selectedTargets, setSelectedTargets] = useState([]);

    useEffect(() => {
        if (allColumns.length > 0 && available.length === 0 && targetCols.length === 0 && !groupCol) {
            setAvailable(allColumns);
        }
    }, [allColumns]);

    const moveRightTarget = () => {
        const toMove = selectedAvailable.filter(c => !groupCol || c.name !== groupCol.name);
        setTargetCols([...targetCols, ...toMove]);
        setAvailable(available.filter(c => !toMove.includes(c)));
        setSelectedAvailable([]);
    };

    const moveRightGroup = () => {
        if (selectedAvailable.length !== 1) return;
        const col = selectedAvailable[0];
        setGroupCol(col);
        setAvailable(available.filter(c => c !== col));
        setSelectedAvailable([]);
    };

    const moveLeftTarget = () => {
        setAvailable([...available, ...selectedTargets]);
        setTargetCols(targetCols.filter(c => !selectedTargets.includes(c)));
        setSelectedTargets([]);
    };

    const removeGroup = () => {
        if (groupCol) {
            setAvailable([...available, groupCol]);
            setGroupCol(null);
        }
    };

    const renderItem = (col, isSelected, onClick) => (
        <div
            key={col.name}
            onClick={onClick}
            className={`flex items-center gap-3 px-3 py-1.5 cursor-pointer select-none transition-colors border-b border-dashed border-slate-100 last:border-0
                 ${isSelected ? 'bg-indigo-50 text-indigo-900' : 'hover:bg-slate-50 text-slate-600'}`}
        >
            <TypeIcon type={col.type} />
            <span className={`text-xs font-mono truncate ${isSelected ? 'font-bold' : ''}`} title={col.name}>{col.name}</span>
        </div>
    );

    return (
        <div className="flex flex-col h-full bg-white font-sans">
            <div className="p-4 border-b border-slate-300">
                <h2 className="text-xs font-bold uppercase tracking-[0.1em] text-slate-900">
                    Конфигурация
                </h2>
            </div>

            <div className="flex flex-col flex-1 overflow-hidden p-4 gap-4 min-h-0">

                {/* Available List */}
                <div className="flex-1 flex flex-col border border-slate-300 min-h-0">
                    <div className="bg-slate-100 px-3 py-1.5 border-b border-slate-300 flex justify-between items-center">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">Доступные</span>
                        <span className="text-[10px] font-mono font-bold text-slate-400">{available.length}</span>
                    </div>
                    <div className="flex-1 overflow-y-auto custom-scrollbar bg-white">
                        {available.map(col => renderItem(
                            col,
                            selectedAvailable.includes(col),
                            () => {
                                if (selectedAvailable.includes(col)) setSelectedAvailable(selectedAvailable.filter(c => c !== col));
                                else setSelectedAvailable([...selectedAvailable, col]);
                            }
                        ))}
                    </div>
                </div>

                {/* Actions */}
                <div className="flex justify-center gap-2">
                    <button
                        onClick={moveRightTarget}
                        disabled={selectedAvailable.length === 0}
                        className="border border-slate-300 px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest hover:bg-slate-900 hover:text-white hover:border-slate-900 disabled:opacity-20 transition-all"
                    >
                        Добавить Y ↓
                    </button>
                    <button
                        onClick={moveLeftTarget}
                        disabled={selectedTargets.length === 0}
                        className="border border-slate-300 px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest hover:bg-red-600 hover:text-white hover:border-red-600 disabled:opacity-20 transition-all"
                    >
                        Убрать ↑
                    </button>
                </div>

                {/* Target Lists */}
                <div className="flex-1 flex flex-col gap-4 min-h-0">

                    {/* Y Variables */}
                    <div className="flex-1 flex flex-col border border-slate-300 bg-slate-50/30 min-h-0">
                        <div className="bg-slate-100 px-3 py-1.5 border-b border-slate-300 flex justify-between items-center">
                            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">Зависимые (Y)</span>
                            <span className="text-[10px] font-mono font-bold text-slate-400">{targetCols.length}</span>
                        </div>
                        <div className="flex-1 overflow-y-auto custom-scrollbar relative">
                            {targetCols.length === 0 && (
                                <div className="absolute inset-0 flex items-center justify-center text-[9px] text-slate-300 uppercase tracking-widest">
                                    Пусто
                                </div>
                            )}
                            {targetCols.map(col => renderItem(
                                col,
                                selectedTargets.includes(col),
                                () => {
                                    if (selectedTargets.includes(col)) setSelectedTargets(selectedTargets.filter(c => c !== col));
                                    else setSelectedTargets([...selectedTargets, col]);
                                }
                            ))}
                        </div>
                    </div>

                    {/* Grouping */}
                    <div className="h-[80px] flex flex-col border border-slate-300 bg-slate-50/30 flex-shrink-0">
                        <div className="bg-slate-100 px-3 py-1.5 border-b border-slate-300 flex justify-between items-center">
                            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">Группирующая (X)</span>
                            <button
                                onClick={moveRightGroup}
                                disabled={selectedAvailable.length !== 1 || !!groupCol}
                                className="text-[9px] font-bold uppercase hover:underline disabled:opacity-0"
                            >
                                Назначить
                            </button>
                        </div>
                        <div className="flex-1 flex items-center justify-center">
                            {groupCol ? (
                                <div className="w-full flex items-center justify-between px-3">
                                    <div className="flex items-center gap-2">
                                        <TypeIcon type={groupCol.type} />
                                        <span className="text-xs font-mono font-bold">{groupCol.name}</span>
                                    </div>
                                    <button onClick={removeGroup} className="text-slate-400 hover:text-red-500 font-bold">×</button>
                                </div>
                            ) : (
                                <div className="text-[9px] text-slate-300 uppercase tracking-widest">Не выбрано</div>
                            )}
                        </div>
                    </div>
                </div>

                <button
                    onClick={() => onRun(targetCols.map(c => c.name), groupCol ? groupCol.name : null)}
                    disabled={!targetCols.length || !groupCol || loading}
                    className="w-full py-3 bg-slate-900 text-white text-[10px] font-bold uppercase tracking-[0.15em] hover:bg-black disabled:bg-slate-200 disabled:text-slate-400 transition-all cursor-pointer"
                >
                    {loading ? 'ОБРАБОТКА...' : 'ЗАПУСТИТЬ АНАЛИЗ'}
                </button>
            </div>
        </div>
    );
}
