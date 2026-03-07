import React, { forwardRef } from 'react';

export function TypeIcon({ type }) {
    switch (type) {
        case 'numeric': return <span className="text-[10px] font-bold text-[color:var(--text-primary)] bg-[color:var(--white)] px-1 py-0.5 rounded-[2px] border border-black">#</span>;
        case 'categorical': return <span className="text-[10px] font-bold text-[color:var(--text-primary)] bg-[color:var(--white)] px-1 py-0.5 rounded-[2px] border border-[color:var(--accent)]">Ab</span>;
        case 'datetime': return <span className="text-[10px] font-bold text-[color:var(--text-primary)] bg-[color:var(--white)] px-1 py-0.5 rounded-[2px] border border-[color:var(--border-color)]">⏱</span>;
        default: return <span className="text-[10px] font-bold text-[color:var(--text-secondary)] bg-[color:var(--white)] px-1 py-0.5 rounded-[2px] border border-[color:var(--border-color)]">T</span>;
    }
}

const ColumnMenu = forwardRef(function ColumnMenu({
    activeMenu, profileTypeByName, handleAction, applyQualityAction, setActiveMenu,
}, ref) {
    if (!activeMenu) return null;
    const colType = profileTypeByName?.[activeMenu.colName];
    const canNormalizeCategories = colType === 'categorical' || colType === 'text';
    return (
        <div
            ref={ref}
            className="absolute bg-[color:var(--white)] rounded-[2px] border border-black w-48 z-50 text-sm overflow-hidden"
            style={{ top: activeMenu.y, left: activeMenu.x }}
        >
            <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)] font-semibold text-[color:var(--text-primary)] truncate">
                {activeMenu.colName}
            </div>
            <div className="p-1 space-y-0.5">
                <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'numeric' })} className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] flex items-center gap-2 transition-colors">
                    <span className="w-4 text-center text-xs font-bold text-[color:var(--text-primary)]">#</span> Число
                </button>
                <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'text' })} className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] flex items-center gap-2 transition-colors">
                    <span className="w-4 text-center text-xs font-bold text-[color:var(--text-secondary)]">T</span> Текст
                </button>
                <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'categorical' })} className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] flex items-center gap-2 transition-colors">
                    <span className="w-4 text-center text-xs font-bold text-[color:var(--accent)]">Ab</span> Категория
                </button>
            </div>
            <div className="border-t border-[color:var(--border-color)] p-1">
                {canNormalizeCategories ? (
                    <button
                        onClick={async () => {
                            const col = activeMenu.colName;
                            setActiveMenu(null);
                            await applyQualityAction({ column: col, action: 'normalize_categories' });
                        }}
                        className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] transition-colors"
                    >
                        Нормализовать категории
                    </button>
                ) : null}
                <button
                    onClick={() => {
                        const newName = prompt("Переименовать столбец:", activeMenu.colName);
                        if (newName && newName !== activeMenu.colName) handleAction({ type: 'rename_col', column: activeMenu.colName, new_name: newName });
                    }}
                    className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] transition-colors"
                >
                    Переименовать
                </button>
                <button
                    onClick={() => {
                        if (confirm(`Удалить столбец "${activeMenu.colName}"?`)) handleAction({ type: 'drop_col', column: activeMenu.colName });
                    }}
                    className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--accent)] rounded-[2px] transition-colors"
                >
                    Удалить
                </button>
            </div>
        </div>
    );
});

export default ColumnMenu;
