import React from 'react';
import { Link } from 'react-router-dom';

const MISSING_MOSTLY_EMPTY_THRESHOLD_PCT = 99.5;
const isMostlyEmptyMissingPct = (pct) => Number(pct) >= MISSING_MOSTLY_EMPTY_THRESHOLD_PCT;

export function PrepOverview({
    piiCandidates, handleDropColumns, loading, goToPrepStep,
    mixedTypeIssues, handleToNumeric, missingColumns, applyQualityAction,
    logLoading, deltaEntries, cleaningLog, cleaningActions,
}) {
    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Чувствительные колонки</div>
                    <button
                        type="button"
                        onClick={() => handleDropColumns(piiCandidates)}
                        disabled={loading || piiCandidates.length === 0}
                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black disabled:opacity-50"
                    >
                        Удалить все
                    </button>
                </div>
                <div className="p-3 space-y-2">
                    {piiCandidates.length ? (
                        <div className="space-y-1">
                            {piiCandidates.slice(0, 8).map((name) => (
                                <div key={name} className="flex items-center justify-between gap-2">
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{name}</div>
                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)]">похоже на ФИО/контакты</div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => handleDropColumns([name])}
                                        className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                    >
                                        Удалить
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-[color:var(--text-secondary)]">Подозрительных колонок не найдено.</div>
                    )}
                </div>
            </div>

            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Смешанные типы</div>
                    <button
                        type="button"
                        onClick={() => goToPrepStep('cleanup')}
                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                    >
                        Открыть
                    </button>
                </div>
                <div className="p-3 space-y-2">
                    {mixedTypeIssues.length ? (
                        <div className="space-y-1">
                            {mixedTypeIssues.slice(0, 6).map((i) => (
                                <div key={i.column} className="flex items-center justify-between gap-2">
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{i.column}</div>
                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)] truncate">{i.polluters?.[0] ? `пример: ${String(i.polluters[0])}` : (i.details || 'разнородные значения')}</div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => handleToNumeric(i.column)}
                                        className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                    >
                                        В числа
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-[color:var(--text-secondary)]">Проблем смешанных типов не найдено.</div>
                    )}
                </div>
            </div>

            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Пропуски</div>
                    <button
                        type="button"
                        onClick={() => goToPrepStep('missing')}
                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                    >
                        Открыть
                    </button>
                </div>
                <div className="p-3 space-y-2">
                    <div className="text-xs text-[color:var(--text-secondary)]">Колонок с пропусками: <span className="font-semibold text-[color:var(--text-primary)]">{missingColumns.length}</span></div>
                    {missingColumns.length ? (
                        <div className="space-y-1">
                            {missingColumns.slice(0, 6).map((r) => {
                                const pct = Number(r?.missing_pct || 0);
                                const mostlyEmpty = isMostlyEmptyMissingPct(pct);
                                const name = r?.original_name;
                                return (
                                    <div key={r?.original_name} className="flex items-center justify-between gap-2">
                                        <div className="min-w-0">
                                            <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{name}</div>
                                            <div className="text-[10px] font-mono text-[color:var(--text-muted)]">{pct}% пропусков</div>
                                        </div>
                                        {mostlyEmpty ? (
                                            <button
                                                type="button"
                                                onClick={() => handleDropColumns([name])}
                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                                            >
                                                Удалить столбец
                                            </button>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={() => applyQualityAction({ column: name, action: 'drop_na' })}
                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                            >
                                                Удалить строки
                                            </button>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    ) : null}
                </div>
            </div>

            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">История очистки</div>
                    <div className="text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">
                        {logLoading ? '…' : `${deltaEntries.length}`}
                    </div>
                </div>
                <div className="p-3 space-y-2">
                    {logLoading ? (
                        <div className="text-xs text-[color:var(--text-secondary)]">Загружаю лог…</div>
                    ) : (
                        <>
                            {cleaningLog?.action ? (
                                <div className="text-xs text-[color:var(--text-secondary)]">
                                    Последнее действие: <span className="font-semibold text-[color:var(--text-primary)]">{String(cleaningLog.action)}</span>
                                </div>
                            ) : null}
                            {cleaningActions.length ? (
                                <div className="text-[11px] font-mono text-[color:var(--text-secondary)] space-y-1">
                                    {cleaningActions.slice(0, 4).map((a, idx) => (
                                        <div key={`${a?.type || 'auto'}-${idx}`}>
                                            — {String(a?.type || 'auto')} {a?.column ? `(${a.column})` : ''}
                                        </div>
                                    ))}
                                    {cleaningActions.length > 4 ? (
                                        <div>…и ещё {cleaningActions.length - 4}</div>
                                    ) : null}
                                </div>
                            ) : (
                                <div className="text-xs text-[color:var(--text-secondary)]">Авто‑очистка не выполнялась.</div>
                            )}
                            {deltaEntries.length ? (
                                <div className="pt-2 text-[11px] font-mono text-[color:var(--text-secondary)] space-y-1">
                                    {deltaEntries.map((e, idx) => (
                                        <div key={`delta-${idx}`}>
                                            • {String(e?.action || 'update')} · {String(e?.ts || '')}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-xs text-[color:var(--text-secondary)]">История изменений пуста.</div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

export function PrepCleanup({
    mixedTypeIssues, handleToNumeric, handleDropColumns,
    piiCandidates, loading,
}) {
    return (
        <div className="space-y-3">
            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Смешанные типы (цифры + текст)</div>
                    <div className="text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">{mixedTypeIssues.length}</div>
                </div>
                <div className="p-3">
                    {mixedTypeIssues.length ? (
                        <div className="space-y-2">
                            {mixedTypeIssues.map((i) => (
                                <div key={i.column} className="flex flex-col md:flex-row md:items-center justify-between gap-2 rounded-[2px] border border-[color:var(--border-color)] px-3 py-2">
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{i.column}</div>
                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)] truncate">{i.polluters?.length ? `пример: ${String(i.polluters[0])}` : (i.details || '')}</div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            type="button"
                                            onClick={() => handleToNumeric(i.column)}
                                            className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                        >
                                            В числа
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => handleDropColumns([i.column])}
                                            className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                                        >
                                            Удалить
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-[color:var(--text-secondary)]">Проблемных колонок не найдено.</div>
                    )}
                </div>
            </div>

            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">ФИО / контакты</div>
                    <button
                        type="button"
                        onClick={() => handleDropColumns(piiCandidates)}
                        disabled={loading || piiCandidates.length === 0}
                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black disabled:opacity-50"
                    >
                        Удалить все
                    </button>
                </div>
                <div className="p-3">
                    {piiCandidates.length ? (
                        <div className="space-y-2">
                            {piiCandidates.map((name) => (
                                <div key={name} className="flex items-center justify-between gap-2 rounded-[2px] border border-[color:var(--border-color)] px-3 py-2">
                                    <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate min-w-0">{name}</div>
                                    <button
                                        type="button"
                                        onClick={() => handleDropColumns([name])}
                                        className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                                    >
                                        Удалить
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-[color:var(--text-secondary)]">По названиям колонок ФИО/контакты не определились.</div>
                    )}
                </div>
            </div>
        </div>
    );
}

export function PrepMissing({
    missingColumns, applyQualityAction, handleDropColumns,
    profileTypeByName,
}) {
    return (
        <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
            <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                <div>
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Пропуски</div>
                    <div className="text-xs text-[color:var(--text-secondary)]">Выбирай действие по каждой колонке — без отката.</div>
                </div>
                <button
                    type="button"
                    onClick={() => applyQualityAction({ mice: true })}
                    className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                >
                    MICE (числовые)
                </button>
            </div>
            <div className="p-3">
                {missingColumns.length ? (
                    <div className="space-y-2">
                        {missingColumns.map((r) => {
                            const name = r?.original_name;
                            const pct = Number(r?.missing_pct || 0);
                            const mostlyEmpty = isMostlyEmptyMissingPct(pct);
                            const t = name ? profileTypeByName[name] : null;
                            const fillAction = t === 'numeric' ? 'fill_mean' : t === 'datetime' ? 'fill_locf' : 'fill_mode';

                            return (
                                <div key={name} className="flex flex-col lg:flex-row lg:items-center justify-between gap-2 rounded-[2px] border border-[color:var(--border-color)] px-3 py-2">
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{name}</div>
                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)]">{pct}% пропусков</div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {mostlyEmpty ? (
                                            <button
                                                type="button"
                                                onClick={() => handleDropColumns([name])}
                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                                            >
                                                Удалить столбец
                                            </button>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={() => applyQualityAction({ column: name, action: 'drop_na' })}
                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                            >
                                                Удалить строки
                                            </button>
                                        )}
                                        <button
                                            type="button"
                                            onClick={() => applyQualityAction({ column: name, action: fillAction })}
                                            disabled={mostlyEmpty}
                                            className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black disabled:opacity-50"
                                        >
                                            Заполнить
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="text-xs text-[color:var(--text-secondary)]">Пропусков не найдено.</div>
                )}
            </div>
        </div>
    );
}

export function PrepDerived({
    derivedOp, setDerivedOp, derivedName, setDerivedName,
    derivedA, setDerivedA, derivedB, setDerivedB,
    derivedSource, setDerivedSource, derivedThreshold, setDerivedThreshold,
    allColumnNames, handleComputeDerived,
}) {
    return (
        <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
            <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)]">
                <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Новые колонки</div>
                <div className="text-xs text-[color:var(--text-secondary)]">Разница и индикаторы — для подготовки исходов/групп.</div>
            </div>
            <div className="p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                    <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">Операция</div>
                    <select
                        value={derivedOp}
                        onChange={(e) => setDerivedOp(e.target.value)}
                        className="h-9 w-full bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
                    >
                        <option value="difference">Разница (A - B)</option>
                        <option value="indicator">Индикатор (≥ порога)</option>
                    </select>
                </div>

                <div>
                    <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">Имя</div>
                    <input
                        value={derivedName}
                        onChange={(e) => setDerivedName(e.target.value)}
                        placeholder="например: delta_score"
                        className="h-9 w-full px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                    />
                </div>

                {derivedOp === 'difference' ? (
                    <>
                        <div>
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">A</div>
                            <select
                                value={derivedA}
                                onChange={(e) => setDerivedA(e.target.value)}
                                className="h-9 w-full bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
                            >
                                <option value="">Выбери колонку</option>
                                {allColumnNames.map((n) => (
                                    <option key={n} value={n}>{n}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">B</div>
                            <select
                                value={derivedB}
                                onChange={(e) => setDerivedB(e.target.value)}
                                className="h-9 w-full bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
                            >
                                <option value="">Выбери колонку</option>
                                {allColumnNames.map((n) => (
                                    <option key={n} value={n}>{n}</option>
                                ))}
                            </select>
                        </div>
                    </>
                ) : (
                    <>
                        <div>
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">Источник</div>
                            <select
                                value={derivedSource}
                                onChange={(e) => setDerivedSource(e.target.value)}
                                className="h-9 w-full bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
                            >
                                <option value="">Выбери колонку</option>
                                {allColumnNames.map((n) => (
                                    <option key={n} value={n}>{n}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">Порог</div>
                            <input
                                value={derivedThreshold}
                                onChange={(e) => setDerivedThreshold(e.target.value)}
                                placeholder="например: 10"
                                className="h-9 w-full px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                            />
                        </div>
                    </>
                )}
            </div>
            <div className="px-3 pb-3">
                <button
                    type="button"
                    onClick={handleComputeDerived}
                    className="h-9 px-4 rounded-[2px] border border-black bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold tracking-[0.18em] uppercase"
                >
                    Добавить колонку
                </button>
            </div>
        </div>
    );
}

export function PrepDone({ id }) {
    return (
        <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
            <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)]">
                <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Готово</div>
                <div className="text-xs text-[color:var(--text-secondary)]">Это отдельный датасет. Можно откатить последние изменения.</div>
            </div>
            <div className="p-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="text-sm font-semibold text-[color:var(--text-primary)]">Дальше по потоку</div>
                <div className="flex items-center gap-2">
                    <Link
                        to={`/prep/${id}`}
                        className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-bold tracking-[0.18em] uppercase hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                    >
                        Переменные
                    </Link>
                    <Link
                        to={`/sorcerer?dataset=${encodeURIComponent(id)}`}
                        className="h-9 px-3 rounded-[2px] border border-black bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold tracking-[0.18em] uppercase"
                    >
                        Согласовать дизайн
                    </Link>
                </div>
            </div>
        </div>
    );
}
