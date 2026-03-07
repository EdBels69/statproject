import { useState, useEffect, useMemo, useCallback, lazy, Suspense } from 'react';
import { useParams, useLocation, Link, useNavigate } from 'react-router-dom';
import ColumnMenu, { TypeIcon } from './profile/ColumnMenu';
import { PrepOverview, PrepCleanup, PrepMissing, PrepDerived, PrepDone } from './profile/PrepStepPanels';
import useProfileData from './profile/useProfileData';
import useVariableMapping from './profile/useVariableMapping';
import usePrepareMode from './profile/usePrepareMode';

const EditableDataGrid = lazy(() => import('../components/EditableDataGrid'));

const MISSING_MOSTLY_EMPTY_THRESHOLD_PCT = 99.5;
const isMostlyEmptyMissingPct = (pct) => Number(pct) >= MISSING_MOSTLY_EMPTY_THRESHOLD_PCT;

export default function Profile() {
    const { id } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const isPrepareMode = Boolean(location?.pathname?.startsWith('/prepare/'));

    const [workspaceView, setWorkspaceView] = useState(() => (
        location?.pathname?.startsWith('/prep/') ? 'variables' : 'data'
    ));

    useEffect(() => {
        if (location?.pathname?.startsWith('/prep/')) setWorkspaceView('variables');
    }, [location?.pathname]);

    useEffect(() => {
        if (isPrepareMode) setWorkspaceView('data');
    }, [isPrepareMode]);

    // Core data hook
    const pd = useProfileData({ id, isPrepareMode, locationState: location.state, navigate });

    // Variable mapping hook
    const vm = useVariableMapping({ id, profile: pd.profile });

    // Preparation mode hook
    const prep = usePrepareMode({
        id, isPrepareMode,
        profile: pd.profile, setProfile: pd.setProfile,
        setPage: pd.setPage,
        setDataReloadKey: pd.setDataReloadKey,
        setLoading: pd.setLoading,
        setError: pd.setError,
        profileTypeByName: pd.profileTypeByName,
        workspaceRows: vm.workspaceRows,
    });

    // Extended handleAction that also refreshes prep state
    const handleAction = useCallback(
        async (action) => {
            pd.setLoading(true);
            pd.setError(null);
            pd.setActiveMenu(null);
            try {
                const { modifyDataset } = await import('../../lib/api');
                const updatedProfile = await modifyDataset(id, [action], { page: pd.page, limit: pd.PAGE_SIZE });
                pd.setProfile(updatedProfile);
                pd.setDataReloadKey((v) => v + 1);
                if (typeof updatedProfile?.page === 'number' && updatedProfile.page !== pd.page) {
                    pd.setPage(updatedProfile.page);
                }
            } catch (err) {
                pd.setError(err.message);
            } finally {
                pd.setLoading(false);
            }
        },
        [id, pd]
    );

    const handleDeleteDatasetColumn = useCallback(
        async (colName) => {
            if (!colName) return;
            if (!confirm(`Удалить столбец "${colName}"?`)) return;
            await handleAction({ type: 'drop_col', column: colName });
            vm.setVariableMapping((prev) => {
                const safePrev = prev && typeof prev === 'object' ? prev : {};
                if (!Object.prototype.hasOwnProperty.call(safePrev, colName)) return prev;
                const next = { ...safePrev };
                delete next[colName];
                vm.scheduleSaveMapping(next);
                return next;
            });
        },
        [handleAction, vm]
    );

    // Actions column def (needs handleDeleteDatasetColumn)
    const actionsColumnDef = useMemo(() => ({
        headerName: 'Действия',
        field: '__actions__',
        editable: false,
        width: 130,
        sortable: false,
        filter: false,
        resizable: false,
        suppressMovable: true,
        cellRenderer: (p) => {
            const name = p?.data?.original_name;
            if (!name) return null;
            return (
                <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleDeleteDatasetColumn(name); }}
                    className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                >
                    Удалить
                </button>
            );
        },
    }), [handleDeleteDatasetColumn]);

    const workspaceColumnDefs = useMemo(() => [
        ...vm.workspaceColumnDefs,
        actionsColumnDef,
    ], [vm.workspaceColumnDefs, actionsColumnDef]);

    const gridFallback = useMemo(() => (
        <div className="animate-pulse" style={{
            minHeight: 320, borderRadius: '2px', border: '1px solid var(--border-color)',
            background: 'var(--bg-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--text-muted)', fontSize: '12px',
        }}>
            Загружаю таблицу…
        </div>
    ), []);

    if (!pd.profile) {
        return (
            <div className="flex items-center justify-center h-screen bg-[color:var(--bg-secondary)]">
                <div className="text-center">
                    <div className="text-4xl mb-4 animate-spin">🌀</div>
                    <p className="text-[color:var(--text-secondary)] font-semibold">Загрузка данных...</p>
                    {pd.error && <p className="text-[color:var(--text-primary)] mt-2">{pd.error}</p>}
                </div>
            </div>
        );
    }

    // Prep step panels
    const prepOverview = (
        <PrepOverview
            piiCandidates={prep.piiCandidates} handleDropColumns={prep.handleDropColumns} loading={pd.loading}
            goToPrepStep={prep.goToPrepStep} mixedTypeIssues={prep.mixedTypeIssues} handleToNumeric={prep.handleToNumeric}
            missingColumns={prep.missingColumns} applyQualityAction={prep.applyQualityAction}
            logLoading={prep.logLoading} deltaEntries={prep.deltaEntries} cleaningLog={prep.cleaningLog} cleaningActions={prep.cleaningActions}
        />
    );
    const prepCleanup = (
        <PrepCleanup
            mixedTypeIssues={prep.mixedTypeIssues} handleToNumeric={prep.handleToNumeric}
            handleDropColumns={prep.handleDropColumns} piiCandidates={prep.piiCandidates} loading={pd.loading}
        />
    );
    const prepMissing = (
        <PrepMissing
            missingColumns={prep.missingColumns} applyQualityAction={prep.applyQualityAction}
            handleDropColumns={prep.handleDropColumns} profileTypeByName={pd.profileTypeByName}
        />
    );
    const prepDerived = (
        <PrepDerived
            derivedOp={prep.derivedOp} setDerivedOp={prep.setDerivedOp}
            derivedName={prep.derivedName} setDerivedName={prep.setDerivedName}
            derivedA={prep.derivedA} setDerivedA={prep.setDerivedA}
            derivedB={prep.derivedB} setDerivedB={prep.setDerivedB}
            derivedSource={prep.derivedSource} setDerivedSource={prep.setDerivedSource}
            derivedThreshold={prep.derivedThreshold} setDerivedThreshold={prep.setDerivedThreshold}
            allColumnNames={pd.allColumnNames} handleComputeDerived={prep.handleComputeDerived}
        />
    );
    const prepDone = <PrepDone id={id} />;

    const prepPanel = (
        <div className="mb-4">
            <div className="rounded-[2px] border border-black bg-[color:var(--white)] overflow-hidden">
                <div className="px-4 py-3 border-b border-[color:var(--border-color)] flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                    <div className="min-w-0">
                        <div className="text-[10px] font-bold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">Подготовка данных</div>
                        <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">Шаг {prep.safePrepStepIndex + 1} / {prep.PREP_STEPS.length}: {prep.activePrepStep?.label}</div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button type="button" onClick={() => prep.setPrepStepIndex((v) => Math.max(0, v - 1))} disabled={prep.safePrepStepIndex <= 0}
                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50">
                            Назад
                        </button>
                        <button type="button" onClick={() => prep.setPrepStepIndex((v) => Math.min(prep.PREP_STEPS.length - 1, v + 1))} disabled={prep.safePrepStepIndex >= prep.PREP_STEPS.length - 1}
                            className="h-9 px-3 rounded-[2px] border border-black bg-[color:var(--black)] text-[color:var(--white)] text-xs font-semibold disabled:opacity-50">
                            Далее
                        </button>
                    </div>
                </div>

                <div className="px-3 py-2 border-b border-[color:var(--border-color)] overflow-x-auto">
                    <div className="flex items-center gap-2 min-w-max">
                        {prep.PREP_STEPS.map((s, idx) => {
                            const active = idx === prep.safePrepStepIndex;
                            return (
                                <button key={s.id} type="button" onClick={() => prep.setPrepStepIndex(idx)}
                                    className={`h-8 px-3 rounded-[999px] border text-[11px] font-bold tracking-[0.18em] uppercase transition-colors ${active
                                        ? 'bg-[color:var(--accent)] text-[color:var(--white)] border-[color:var(--accent)]'
                                        : 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                        }`}>
                                    {idx + 1}. {s.label}
                                </button>
                            );
                        })}
                        <div className="ml-2 text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">
                            <button type="button" onClick={prep.handleUndoPrepare}
                                disabled={!isPrepareMode || prep.scanLoading || pd.loading || prep.prepUndoLoading || prep.prepHistoryCount <= 0}
                                className="h-7 px-2 rounded-[999px] border border-[color:var(--border-color)] text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-muted)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50">
                                Откат{prep.prepHistoryCount > 0 ? ` (${prep.prepHistoryCount})` : ''}
                            </button>
                        </div>
                    </div>
                </div>

                <div className="p-3 bg-[color:var(--bg-secondary)]">
                    {prep.activePrepStep?.id === 'overview' ? prepOverview : null}
                    {prep.activePrepStep?.id === 'cleanup' ? prepCleanup : null}
                    {prep.activePrepStep?.id === 'missing' ? prepMissing : null}
                    {prep.activePrepStep?.id === 'derived' ? prepDerived : null}
                    {prep.activePrepStep?.id === 'done' ? prepDone : null}
                </div>
            </div>
        </div>
    );

    return (
        <div className="min-h-screen bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)] font-sans"
            onClick={() => { pd.setActiveMenu(null); prep.setQualityOpen(false); }}>

            {/* Header */}
            <div className="bg-white border-b border-[color:var(--border-color)] px-6 py-3">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-lg font-bold text-[color:var(--text-primary)]">{pd.filename}</h1>
                        <div className="text-xs text-[color:var(--text-secondary)]">
                            {pd.profile.row_count} строк • {pd.profile.col_count} столбцов
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {!isPrepareMode && (
                            <button type="button" onClick={pd.handleStartPreparation}
                                className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-bold tracking-[0.18em] uppercase hover:border-black hover:bg-[color:var(--bg-tertiary)]">
                                Подготовка данных
                            </button>
                        )}
                        <Link to={`/protocol?dataset=${encodeURIComponent(id)}`}
                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-primary)] text-xs font-bold tracking-[0.18em] uppercase inline-flex items-center justify-center hover:border-black hover:bg-[color:var(--bg-tertiary)]">
                            Авто‑отчёт
                        </Link>
                        <Link to={`/sorcerer?dataset=${encodeURIComponent(id)}`}
                            className="h-9 px-3 rounded-[2px] border border-black bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold tracking-[0.18em] uppercase inline-flex items-center justify-center">
                            Согласовать дизайн
                        </Link>
                        {pd.sheets.length > 0 && (
                            <select className="h-9 bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
                                onChange={(e) => pd.handleSheetChange(e.target.value)}
                                value={pd.selectedSheet || pd.sheets[0] || ""}>
                                {pd.sheets.map(sheet => <option key={sheet} value={sheet}>{sheet}</option>)}
                            </select>
                        )}
                    </div>
                </div>
            </div>

            <main className="max-w-full p-4">
                {isPrepareMode ? prepPanel : null}

                {/* Main Data Grid */}
                <div className="bg-white rounded border border-[color:var(--border-color)] flex flex-col overflow-hidden min-h-[500px] relative"
                    style={{ height: 'min(800px, calc(100vh - 180px))' }}>

                    {(pd.loading || pd.dataLoading) && (
                        <div className="absolute inset-0 bg-[color:var(--white)]/80 z-20 flex items-center justify-center">
                            <div className="bg-[color:var(--white)] p-4 rounded-[2px] border border-[color:var(--border-color)] flex items-center gap-3">
                                <div className="w-4 h-4 border-2 border-[color:var(--accent)] border-t-transparent rounded-[2px] animate-spin"></div>
                                <span className="text-sm font-semibold text-[color:var(--text-primary)]">Проверяю данные…</span>
                            </div>
                        </div>
                    )}

                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 px-4 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
                        <div className="flex items-center gap-2">
                            <button type="button" onClick={() => setWorkspaceView('data')}
                                className={`h-9 px-4 min-w-[160px] rounded-[2px] text-xs font-bold uppercase tracking-[0.18em] border transition-colors inline-flex items-center justify-center ${workspaceView === 'data'
                                    ? 'bg-[color:var(--black)] text-[color:var(--white)] border-[color:var(--black)]'
                                    : 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                    }`}>
                                ДАННЫЕ
                            </button>
                            <button type="button" onClick={() => setWorkspaceView('variables')}
                                className={`h-9 px-4 min-w-[160px] rounded-[2px] text-xs font-bold uppercase tracking-[0.18em] border transition-colors inline-flex items-center justify-center ${workspaceView === 'variables'
                                    ? 'bg-[color:var(--accent)] text-[color:var(--white)] border-[color:var(--accent)]'
                                    : 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                    }`}>
                                ЛИСТ ПЕРЕМЕННЫХ
                            </button>
                            {workspaceView === 'variables' && (
                                <div className="flex items-center gap-2 ml-2">
                                    <input value={vm.mappingFilter} onChange={(e) => vm.setMappingFilter(e.target.value)} placeholder="Поиск…"
                                        className="h-9 w-56 px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]" />
                                    <div className="relative">
                                        <button type="button" onClick={(e) => { e.stopPropagation(); prep.setQualityOpen((v) => !v); }}
                                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                                            title="Рекомендации по пропускам">
                                            Пропуски: {prep.missingColumns.length}
                                        </button>
                                        {prep.qualityOpen && (
                                            <div className="absolute right-0 mt-2 w-[520px] max-w-[80vw] bg-[color:var(--white)] border border-black rounded-[2px] shadow-lg z-30 overflow-hidden"
                                                onClick={(e) => e.stopPropagation()}>
                                                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                                                    <div className="text-xs font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Рекомендации по пропускам</div>
                                                    <button type="button" onClick={() => prep.setQualityOpen(false)}
                                                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold hover:border-black">Закрыть</button>
                                                </div>
                                                <div className="p-3 space-y-2">
                                                    <div className="flex items-center justify-between gap-2">
                                                        <div className="text-xs text-[color:var(--text-secondary)]">Сначала обработай столбцы с высоким % пропусков.</div>
                                                        <button type="button" onClick={() => prep.applyQualityAction({ mice: true })}
                                                            className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)]">
                                                            MICE (числовые)
                                                        </button>
                                                    </div>
                                                    <div className="max-h-64 overflow-auto custom-scrollbar divide-y divide-[color:var(--border-color)] border border-[color:var(--border-color)] rounded-[2px]">
                                                        {prep.missingColumns.slice(0, 8).map((r) => {
                                                            const name = r?.original_name;
                                                            const pct = Number(r?.missing_pct || 0);
                                                            const mostlyEmpty = isMostlyEmptyMissingPct(pct);
                                                            const t = name ? pd.profileTypeByName[name] : null;
                                                            const fillAction = t === 'numeric' ? 'fill_mean' : t === 'datetime' ? 'fill_locf' : 'fill_mode';
                                                            return (
                                                                <div key={name} className="flex items-center gap-3 px-3 py-2">
                                                                    <div className="min-w-0 flex-1">
                                                                        <div className="text-xs font-semibold truncate text-[color:var(--text-primary)]">{name}</div>
                                                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)]">{pct}% пропусков</div>
                                                                    </div>
                                                                    <div className="flex items-center gap-2">
                                                                        {mostlyEmpty ? (
                                                                            <button type="button" onClick={() => prep.handleDropColumns([name])}
                                                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black">Удалить столбец</button>
                                                                        ) : (
                                                                            <button type="button" onClick={() => prep.applyQualityAction({ column: name, action: 'drop_na' })}
                                                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black">Удалить строки</button>
                                                                        )}
                                                                        <button type="button" onClick={() => prep.applyQualityAction({ column: name, action: fillAction })} disabled={mostlyEmpty}
                                                                            className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black disabled:opacity-50">Заполнить</button>
                                                                    </div>
                                                                </div>
                                                            );
                                                        })}
                                                        {prep.missingColumns.length === 0 && (
                                                            <div className="px-3 py-3 text-xs text-[color:var(--text-secondary)]">Пропусков не найдено.</div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                    <div className="hidden lg:flex items-center gap-2">
                                        <input value={vm.bulkSubgroup} onChange={(e) => vm.setBulkSubgroup(e.target.value)} list="subgroup-suggestions" placeholder="Подгруппа"
                                            className="h-9 w-44 px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]" />
                                        <datalist id="subgroup-suggestions">{vm.subgroupSuggestions.map((v) => <option key={v} value={v} />)}</datalist>
                                        <button type="button" onClick={() => vm.applyBulkMappingField('subgroup', vm.bulkSubgroup)}
                                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)]">Применить</button>
                                        <input value={vm.bulkTimepoint} onChange={(e) => vm.setBulkTimepoint(e.target.value)} list="timepoint-suggestions" placeholder="Точка времени"
                                            className="h-9 w-44 px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]" />
                                        <datalist id="timepoint-suggestions">{vm.timepointSuggestions.map((v) => <option key={v} value={v} />)}</datalist>
                                        <button type="button" onClick={() => vm.applyBulkMappingField('timepoint', vm.bulkTimepoint)}
                                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)]">Применить</button>
                                    </div>
                                    <div className="text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">
                                        {vm.mappingLoading ? 'Загрузка' : vm.mappingSaving ? 'Сохранение' : vm.mappingError ? 'Ошибка' : 'Сохранено'}
                                    </div>
                                </div>
                            )}
                        </div>

                        {workspaceView === 'data' ? (
                            <div className="flex items-center gap-2">
                                <input value={pd.dataFilter} onChange={(e) => pd.setDataFilter(e.target.value)} placeholder="Фильтр…"
                                    className="h-9 w-56 px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]" />
                                <div className="hidden md:flex items-center gap-2">
                                    <button type="button" onClick={() => pd.setDataColOffset((v) => Math.max(0, v - pd.dataColLimit))} disabled={pd.loading || pd.dataLoading || pd.dataColOffset <= 0}
                                        className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50">◀︎ Колонки</button>
                                    <button type="button"
                                        onClick={() => { const tc = Number(pd.profile?.col_count || 0); const mo = Math.max(0, tc - Math.max(1, pd.dataColLimit)); pd.setDataColOffset((v) => Math.min(mo, v + pd.dataColLimit)); }}
                                        disabled={pd.loading || pd.dataLoading || (Number(pd.profile?.col_count || 0) > 0 && pd.dataColOffset + pd.dataColLimit >= Number(pd.profile?.col_count || 0))}
                                        className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50">Колонки ▶︎</button>
                                    <input type="number" min={1} max={Math.max(1, pd.maxDataColOffset + 1)} value={Math.max(1, pd.dataColOffset + 1)}
                                        onChange={(e) => { const tc = Number(pd.profile?.col_count || 0); const raw = Number(e.target.value); if (!Number.isFinite(raw)) return; const ms = Math.max(1, Math.max(0, tc - Math.max(1, pd.dataColLimit)) + 1); pd.setDataColOffset(Math.max(1, Math.min(ms, raw)) - 1); }}
                                        className="h-9 w-24 px-2 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]" />
                                    <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">
                                        {Number(pd.profile?.col_count || 0) > 0
                                            ? `Колонки ${pd.dataColOffset + 1}–${Math.min(Number(pd.profile?.col_count || 0), pd.dataColOffset + pd.dataColLimit)} / ${pd.profile.col_count}`
                                            : 'Колонки'}
                                    </div>
                                </div>
                                <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">
                                    Страница {pd.profile.page} / {pd.profile.total_pages}
                                </div>
                                <button type="button" onClick={() => pd.setPage((p) => Math.max(1, p - 1))} disabled={pd.loading || pd.dataLoading || (pd.profile.page || 1) <= 1}
                                    className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50">Назад</button>
                                <button type="button" onClick={() => pd.setPage((p) => Math.min(pd.profile.total_pages || p + 1, p + 1))} disabled={pd.loading || pd.dataLoading || (pd.profile.page || 1) >= (pd.profile.total_pages || 1)}
                                    className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50">Далее</button>
                            </div>
                        ) : (
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">
                                {vm.workspaceRows.length} переменных
                            </div>
                        )}
                    </div>

                    <div className="flex-1 min-h-0">
                        <ColumnMenu ref={pd.menuRef} activeMenu={pd.activeMenu} profileTypeByName={pd.profileTypeByName}
                            handleAction={handleAction} applyQualityAction={prep.applyQualityAction} setActiveMenu={pd.setActiveMenu} />
                        <Suspense fallback={gridFallback}>
                            {workspaceView === 'data' ? (
                                <EditableDataGrid
                                    columns={pd.dataColumns}
                                    rows={pd.dataRows}
                                    quickFilterText={pd.dataFilter}
                                    loading={pd.loading || pd.dataLoading}
                                    onHeaderMenu={pd.handleHeaderMenu}
                                    onDropRow={(rowIndex) => handleAction({ type: 'drop_row', row_index: pd.baseRowIndex + rowIndex })}
                                    onUpdateCell={({ rowIndex, colName, value }) => handleAction({ type: 'update_cell', row_index: pd.baseRowIndex + rowIndex, column: colName, value })}
                                />
                            ) : (
                                <EditableDataGrid
                                    columns={[]}
                                    rows={vm.workspaceRows}
                                    columnDefsOverride={workspaceColumnDefs}
                                    quickFilterText={vm.mappingFilter}
                                    loading={vm.mappingLoading}
                                    onUpdateCell={vm.handleWorkspaceUpdateCell}
                                    onGridReady={(params) => { vm.variableGridApiRef.current = params?.api || null; }}
                                />
                            )}
                        </Suspense>
                    </div>
                </div>
            </main>
        </div>
    );
}
