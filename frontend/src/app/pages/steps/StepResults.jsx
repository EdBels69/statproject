import React, { useMemo, useState, useEffect, lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { applyStrategy, downloadProtocolReport, getAnalysisResults, getProtocolReportUrl } from '../../../lib/api';
import { useTranslation } from '../../../hooks/useTranslation';
import Button from '../../components/ui/Button';
import { useLanguage } from '../../../contexts/LanguageContext';
import {
    BeakerIcon,
    ArrowDownTrayIcon
} from '@heroicons/react/24/outline';

// Contextual Education Components
import { StatTooltip, EffectSizeExplainer, PowerExplainer } from '../../components/education';

const VisualizePlot = lazy(() => import('../../components/VisualizePlot'));
const ClusteredHeatmap = lazy(() => import('../../components/ClusteredHeatmap'));
const InteractionPlot = lazy(() => import('../../components/InteractionPlot'));

const formatNum = (v, digits = 2) => {
    const n = typeof v === 'number' ? v : Number(v);
    if (!Number.isFinite(n)) return '—';
    return n.toFixed(digits);
};

const formatP = (v) => {
    if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
    if (v < 0.001) return '<0.001';
    return v.toFixed(4);
};

const getDeltaFromPlotStats = (plotStats) => {
    if (!plotStats || typeof plotStats !== 'object') return null;
    const keys = Object.keys(plotStats).filter((k) => k && k !== 'overall').sort((a, b) => String(a).localeCompare(String(b)));
    if (keys.length !== 2) return null;
    const a = plotStats[keys[0]];
    const b = plotStats[keys[1]];
    const meanA = typeof a?.mean === 'number' ? a.mean : Number(a?.mean);
    const meanB = typeof b?.mean === 'number' ? b.mean : Number(b?.mean);
    if (!Number.isFinite(meanA) || !Number.isFinite(meanB)) return null;
    const deltaAbs = meanB - meanA;
    const deltaPct = meanA !== 0 ? (deltaAbs / meanA) * 100 : null;
    return {
        a: String(keys[0]),
        b: String(keys[1]),
        delta_abs: deltaAbs,
        delta_pct: (typeof deltaPct === 'number' && Number.isFinite(deltaPct)) ? deltaPct : null,
    };
};

const getPostHocRows = (postHoc) => {
    if (!postHoc) return [];
    const list = Array.isArray(postHoc)
        ? postHoc
        : (Array.isArray(postHoc?.comparisons) ? postHoc.comparisons : []);
    return list
        .map((r) => {
            if (!r || typeof r !== 'object') return null;
            const group1 = r.group1 ?? r.a ?? r.left;
            const group2 = r.group2 ?? r.b ?? r.right;
            if (!group1 || !group2) return null;
            return {
                group1: String(group1),
                group2: String(group2),
                p_value: typeof r.p_value === 'number' ? r.p_value : (typeof r.p === 'number' ? r.p : null),
                p_value_adj: typeof r.p_value_adj === 'number' ? r.p_value_adj : null,
                significant: r.significant,
                significant_adj: r.significant_adj,
            };
        })
        .filter(Boolean)
        .sort((a, b) => (a.group1.localeCompare(b.group1)) || (a.group2.localeCompare(b.group2)));
};

const BatchAnalysisView = ({ data, datasetId, wizardContext, localKey }) => {
    const { t } = useTranslation();
    const { educationLevel } = useLanguage();
    const [query, setQuery] = useState('');
    const [significantOnly, setSignificantOnly] = useState(false);
    const [sortBy, setSortBy] = useState('p');
    const [openKey, setOpenKey] = useState(null);
    const [loadingKey, setLoadingKey] = useState(null);
    const [visibleCount, setVisibleCount] = useState(200);

    const alpha = Number(wizardContext?.variables?.alpha);
    const threshold = Number.isFinite(alpha) ? alpha : 0.05;

    const flatRows = useMemo(() => {
        if (!data || typeof data !== 'object') return [];

        if (data.type === 'timepoint_batch_analysis') {
            const slices = data?.slices && typeof data.slices === 'object' ? data.slices : {};
            return Object.entries(slices)
                .sort(([a], [b]) => String(a).localeCompare(String(b)))
                .flatMap(([slice, sliceRes]) => {
                    const items = Array.isArray(sliceRes?.items) ? sliceRes.items : [];
                    return items
                        .filter((it) => it && it.target)
                        .map((it) => ({ slice: String(slice), item: it }));
                });
        }

        if (data.type === 'batch_analysis') {
            const items = Array.isArray(data?.items) ? data.items : [];
            return items
                .filter((it) => it && it.target)
                .map((it) => ({ slice: null, item: it }));
        }

        return [];
    }, [data]);

    const rows = useMemo(() => {
        const q = String(query || '').trim().toLowerCase();
        const filtered = flatRows
            .map(({ slice, item }) => {
                const pRaw = item?.p_value;
                const pAdj = item?.p_value_adj;
                const pUsed = (typeof pAdj === 'number' && Number.isFinite(pAdj)) ? pAdj : pRaw;
                const isSig = (typeof pUsed === 'number' && Number.isFinite(pUsed)) ? pUsed < threshold : false;
                return {
                    slice,
                    target: String(item?.target),
                    pRaw,
                    pAdj,
                    pUsed,
                    isSig,
                    item,
                };
            })
            .filter((r) => (q ? r.target.toLowerCase().includes(q) : true))
            .filter((r) => (significantOnly ? r.isSig : true));

        const sorted = filtered.slice().sort((a, b) => {
            if (sortBy === 'alpha') {
                if (a.slice !== null && b.slice !== null && String(a.slice) !== String(b.slice)) {
                    return String(a.slice).localeCompare(String(b.slice));
                }
                return a.target.localeCompare(b.target);
            }
            if (sortBy === 'slice') {
                return String(a.slice ?? '').localeCompare(String(b.slice ?? '')) || a.target.localeCompare(b.target);
            }
            const ap = (typeof a.pUsed === 'number' && Number.isFinite(a.pUsed)) ? a.pUsed : 1;
            const bp = (typeof b.pUsed === 'number' && Number.isFinite(b.pUsed)) ? b.pUsed : 1;
            return ap - bp;
        });

        return sorted;
    }, [flatRows, query, significantOnly, sortBy, threshold]);

    const hasSlice = useMemo(() => rows.some((r) => r.slice !== null && r.slice !== undefined), [rows]);

    useEffect(() => {
        setVisibleCount(200);
        setOpenKey(null);
    }, [query, significantOnly, sortBy]);

    const visibleRows = useMemo(() => {
        if (!rows.length) return [];
        const cap = Math.max(1, Number(visibleCount) || 0);
        return rows.slice(0, cap);
    }, [rows, visibleCount]);

    const openInNewTab = (path, key) => {
        const url = `/${path}/${datasetId}?local=${encodeURIComponent(String(key))}`;
        const tab = window.open('about:blank', '_blank');
        if (tab) {
            tab.location.href = url;
            tab.focus();
            return;
        }
        window.open(url, '_blank');
    };

    const storeWizardPayload = (payload) => {
        const fn = globalThis?.crypto?.randomUUID;
        const key = typeof fn === 'function'
            ? fn.call(globalThis.crypto)
            : `w_${Date.now()}_${Math.random().toString(16).slice(2)}`;
        sessionStorage.setItem(`statproject_wizard_run_${key}`, JSON.stringify(payload));
        return key;
    };

    const runDrilldown = async (row) => {
        if (!wizardContext?.variables || !wizardContext?.recommendation) return;

        setLoadingKey(`${String(row.slice)}__${String(row.target)}`);
        try {
            const baseMethodId = String(wizardContext.recommendation?.method_id || '').trim();
            const methodId = data?.type === 'timepoint_batch_analysis' ? 'kruskal' : (data?.method_id || baseMethodId || 'kruskal');
            const vars = {
                ...wizardContext.variables,
                target: row.target,
                all_numeric: false,
            };

            if (data?.type === 'timepoint_batch_analysis' && row.slice) {
                vars.timepoint_value = String(row.slice);
            }

            const res = await applyStrategy({
                recommendation: {
                    method_id: methodId,
                    name: wizardContext.recommendation?.name || methodId,
                    description: wizardContext.recommendation?.description || '',
                    assumptions: wizardContext.recommendation?.assumptions || [],
                },
                variables: vars,
                dataset_id: String(datasetId),
                alpha: vars.alpha,
            });

            const key = storeWizardPayload({
                results: {
                    protocol_name: `Drilldown · ${row.target}`,
                    results: {
                        analysis: res.results,
                    },
                },
                wizard: {
                    variables: vars,
                    recommendation: { ...wizardContext.recommendation, method_id: methodId },
                    datasetId: String(datasetId),
                    parentLocalKey: localKey || null,
                },
            });

            openInNewTab('graphs', key);
        } catch (e) {
            alert(`Ошибка построения графика: ${e?.message || String(e)}`);
        } finally {
            setLoadingKey(null);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Таблица результатов</div>
                    <div className="mt-1 text-sm text-[color:var(--text-secondary)]">Фильтруйте, сортируйте и раскрывайте детали по показателям.</div>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Поиск показателя…"
                        className="h-9 w-[240px] rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 text-sm"
                    />
                    <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                        <input
                            type="checkbox"
                            checked={significantOnly}
                            onChange={(e) => setSignificantOnly(e.target.checked)}
                            className="accent-[color:var(--accent)]"
                        />
                        только значимые
                    </label>
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value)}
                        className="h-9 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                        aria-label="Сортировка"
                    >
                        <option value="p">по p</option>
                        <option value="alpha">A–Z</option>
                        <option value="slice">по точке</option>
                    </select>
                </div>
            </div>

            <div className="overflow-x-auto border border-[color:var(--border-color)] rounded-[2px]">
                <table className="min-w-full divide-y divide-[color:var(--border-color)]">
                    <thead className="bg-[color:var(--bg-secondary)]">
                        <tr>
                            {hasSlice && (
                                <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Точка</th>
                            )}
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Показатель</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Δ</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Δ%</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                                <StatTooltip term="p_value" level={educationLevel}>
                                    <span>p(raw)</span>
                                </StatTooltip>
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                                <StatTooltip term="p_value_adj" level={educationLevel}>
                                    <span>p(adj)</span>
                                </StatTooltip>
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Значимо</th>
                            <th className="px-4 py-3 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Действия</th>
                        </tr>
                    </thead>
                    <tbody className="bg-[color:var(--white)] divide-y divide-[color:var(--border-color)]">
                        {visibleRows.map((r) => {
                            const key = `${String(r.slice)}__${String(r.target)}`;
                            const opened = openKey === key;
                            const delta = getDeltaFromPlotStats(r.item?.plot_stats);
                            return (
                                <React.Fragment key={key}>
                                    <tr>
                                        {hasSlice && (
                                            <td className="px-4 py-3 text-sm text-[color:var(--text-secondary)]">{r.slice ?? '—'}</td>
                                        )}
                                        <td className="px-4 py-3 text-sm font-bold text-[color:var(--text-primary)]">{r.target}</td>
                                        <td className="px-4 py-3 text-sm font-mono text-[color:var(--text-secondary)]">
                                            {delta ? formatNum(delta.delta_abs, 2) : '—'}
                                        </td>
                                        <td className="px-4 py-3 text-sm font-mono text-[color:var(--text-secondary)]">
                                            {delta && typeof delta.delta_pct === 'number' ? `${formatNum(delta.delta_pct, 1)}%` : '—'}
                                        </td>
                                        <td className="px-4 py-3 text-sm font-mono text-[color:var(--text-secondary)]">{formatP(r.pRaw)}</td>
                                        <td className="px-4 py-3 text-sm font-mono font-black text-[color:var(--text-primary)]">{formatP(r.pAdj)}</td>
                                        <td className="px-4 py-3">
                                            <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-[10px] font-black tracking-widest ${r.isSig
                                                ? 'border-[color:var(--success)] text-[color:var(--success)]'
                                                : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}
                                            >
                                                {r.isSig ? 'ДА' : 'НЕТ'}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <button
                                                    type="button"
                                                    onClick={() => setOpenKey(opened ? null : key)}
                                                    className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                                                >
                                                    Детали
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => runDrilldown(r)}
                                                    disabled={!wizardContext?.variables || loadingKey === key}
                                                    className="h-8 px-3 rounded-[2px] border border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-[10px] font-black uppercase tracking-widest text-[color:var(--text-primary)] hover:bg-[color:var(--white)] disabled:opacity-40 transition-colors"
                                                >
                                                    {loadingKey === key ? t('loading') : 'График'}
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                    {opened && (
                                        <tr>
                                            <td colSpan={hasSlice ? 8 : 7} className="px-4 py-4 bg-[color:var(--bg-secondary)]">
                                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                                    <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] p-4">
                                                        <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Описательная статистика</div>
                                                        {delta && (
                                                            <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                                                                Δ({delta.a}→{delta.b}) {formatNum(delta.delta_abs, 2)}{typeof delta.delta_pct === 'number' ? ` (${formatNum(delta.delta_pct, 1)}%)` : ''}
                                                                {r.item?.effect_size_interpretation?.label_ru ? ` · эффект: ${String(r.item.effect_size_interpretation.label_ru)}` : ''}
                                                            </div>
                                                        )}
                                                        <div className="mt-3 overflow-x-auto">
                                                            <table className="min-w-full divide-y divide-[color:var(--border-color)]">
                                                                <thead className="bg-[color:var(--bg-secondary)]">
                                                                    <tr>
                                                                        <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Группа</th>
                                                                        <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">n</th>
                                                                        <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Mean±SD</th>
                                                                        <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Median[IQR]</th>
                                                                        <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Min–Max</th>
                                                                    </tr>
                                                                </thead>
                                                                <tbody className="bg-[color:var(--white)] divide-y divide-[color:var(--border-color)]">
                                                                    {Object.entries(r.item?.plot_stats || {})
                                                                        .filter(([k]) => k && k !== 'overall')
                                                                        .sort(([a], [b]) => String(a).localeCompare(String(b)))
                                                                        .map(([groupName, s]) => (
                                                                            <tr key={String(groupName)}>
                                                                                <td className="px-3 py-2 text-xs font-bold text-[color:var(--text-primary)]">{String(groupName)}</td>
                                                                                <td className="px-3 py-2 text-xs font-mono text-[color:var(--text-secondary)]">{typeof s?.count === 'number' ? String(s.count) : '—'}</td>
                                                                                <td className="px-3 py-2 text-xs font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.mean)} ± ${formatNum(s?.sd)}`}</td>
                                                                                <td className="px-3 py-2 text-xs font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.median)} [${formatNum(s?.q1)}; ${formatNum(s?.q3)}]`}</td>
                                                                                <td className="px-3 py-2 text-xs font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.min)}–${formatNum(s?.max)}`}</td>
                                                                            </tr>
                                                                        ))}
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                    <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] p-4">
                                                        <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Пост‑хок</div>
                                                        <div className="mt-3 overflow-x-auto">
                                                            {getPostHocRows(r.item?.post_hoc).length ? (
                                                                <table className="min-w-full divide-y divide-[color:var(--border-color)]">
                                                                    <thead className="bg-[color:var(--bg-secondary)]">
                                                                        <tr>
                                                                            <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">A</th>
                                                                            <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">B</th>
                                                                            <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">p(raw)</th>
                                                                            <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">p(adj)</th>
                                                                            <th className="px-3 py-2 text-left text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Значимо</th>
                                                                        </tr>
                                                                    </thead>
                                                                    <tbody className="bg-[color:var(--white)] divide-y divide-[color:var(--border-color)]">
                                                                        {getPostHocRows(r.item?.post_hoc).map((ph, idx) => {
                                                                            const raw = ph.p_value;
                                                                            const adj = ph.p_value_adj;
                                                                            const pUsed = (typeof adj === 'number' && Number.isFinite(adj)) ? adj : raw;
                                                                            const sig = ph.significant_adj ?? ph.significant;
                                                                            return (
                                                                                <tr key={`${ph.group1}__${ph.group2}__${idx}`}>
                                                                                    <td className="px-3 py-2 text-xs font-bold text-[color:var(--text-primary)]">{ph.group1}</td>
                                                                                    <td className="px-3 py-2 text-xs font-bold text-[color:var(--text-primary)]">{ph.group2}</td>
                                                                                    <td className="px-3 py-2 text-xs font-mono text-[color:var(--text-secondary)]">{formatP(raw)}</td>
                                                                                    <td className="px-3 py-2 text-xs font-mono font-black text-[color:var(--text-primary)]">{formatP(adj)}</td>
                                                                                    <td className="px-3 py-2">
                                                                                        <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-[10px] font-black tracking-widest ${(typeof pUsed === 'number' && Number.isFinite(pUsed) && pUsed < threshold) || sig
                                                                                            ? 'border-[color:var(--success)] text-[color:var(--success)]'
                                                                                            : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}
                                                                                        >
                                                                                            {(typeof pUsed === 'number' && Number.isFinite(pUsed) && pUsed < threshold) || sig ? 'ДА' : 'НЕТ'}
                                                                                        </span>
                                                                                    </td>
                                                                                </tr>
                                                                            );
                                                                        })}
                                                                    </tbody>
                                                                </table>
                                                            ) : (
                                                                <div className="text-sm text-[color:var(--text-secondary)]">Нет пост‑хок сравнений для этого результата.</div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </React.Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {rows.length > visibleRows.length && (
                <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="text-xs font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">
                        Показано {visibleRows.length} / {rows.length}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                        <button
                            type="button"
                            onClick={() => setVisibleCount((v) => Math.min(rows.length, (Number(v) || 0) + 200))}
                            className="h-9 px-4 rounded-[2px] border border-[color:var(--border-color)] text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                        >
                            Показать ещё
                        </button>
                        <button
                            type="button"
                            onClick={() => setVisibleCount(rows.length)}
                            className="h-9 px-4 rounded-[2px] border border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-[10px] font-black uppercase tracking-widest text-[color:var(--text-primary)] hover:bg-[color:var(--white)] transition-colors"
                        >
                            Показать все
                        </button>
                    </div>
                </div>
            )}

            {!rows.length && (
                <div className="text-sm text-[color:var(--text-secondary)]">{t('no_data')}</div>
            )}
        </div>
    );
};

/* --- SUB-COMPONENT: TABLE 1 (Descriptive) --- */
const Table1View = ({ data }) => {
    const { t } = useTranslation();
    if (!data || !data.data) return <div>{t('no_data')}</div>;
    const stats = data.data; // { "A": {mean, ...}, "B": {mean...}, "overall": {} }
    const groups = Object.keys(stats).filter(k => k !== 'overall');

    const rows = [
        'mean_sd',
        'median_q1_q3',
        'min_max',
        'ci_95'
    ];

    return (
        <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[color:var(--border-color)]">
                <thead className="bg-[color:var(--bg-secondary)]">
                    <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('metric')}</th>
                        {groups.map(g => (
                            <th key={g} className="px-6 py-3 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">
                                {t('group')} {g} ({t('n')}={stats[g]?.count || 0})
                            </th>
                        ))}
                        <th className="px-6 py-3 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider bg-[color:var(--bg-secondary)]">
                            {t('overall')} ({t('n')}={stats['overall']?.count || 0})
                        </th>
                    </tr>
                </thead>
                <tbody className="bg-[color:var(--white)] divide-y divide-[color:var(--border-color)]">
                    {rows.map((rowKey) => (
                        <tr key={rowKey}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-[color:var(--text-primary)]">{t(rowKey)}</td>
                            {groups.map(g => {
                                const s = stats[g];
                                let val = "";
                                if (rowKey === 'mean_sd') val = `${s.mean.toFixed(2)} (${s.std.toFixed(2)})`;
                                if (rowKey === 'median_q1_q3') val = `${s.median.toFixed(2)} [${s.q1.toFixed(2)}, ${s.q3.toFixed(2)}]`;
                                if (rowKey === 'min_max') val = `${s.min.toFixed(2)} - ${s.max.toFixed(2)}`;
                                if (rowKey === 'ci_95') val = `${s.ci_lower?.toFixed(2)} - ${s.ci_upper?.toFixed(2)}`;
                                return <td key={g} className="px-6 py-4 whitespace-nowrap text-sm text-[color:var(--text-secondary)]">{val}</td>
                            })}
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-[color:var(--text-secondary)] bg-[color:var(--bg-secondary)]">
                                {rowKey === 'mean_sd' && stats?.overall?.mean != null ? `${stats.overall.mean.toFixed(2)}` : '-'}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

/* --- SUB-COMPONENT: HYPOTHESIS TEST --- */
const CompareView = ({ result, stepId }) => {
    const { t } = useTranslation();
    const { educationLevel } = useLanguage();
    const methodId = result?.method?.id || result?.type || result?.method;
    const assumptions = result?.assumption_checks || result?.assumptions;
    const methodRequested = result?.method_requested;
    const methodUsed = result?.method_used;
    const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
    const roc = result?.roc;
    const coefficients = Array.isArray(result?.coefficients) ? result.coefficients : [];
    const deltaPlot = getDeltaFromPlotStats(result?.plot_stats);
    const deltaWide = result?.delta?.overall;

    const chartFallback = useMemo(() => (
        <div className="animate-pulse" style={{
            height: 360,
            borderRadius: '2px',
            border: '1px solid var(--border-color)',
            background: 'var(--bg-secondary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-secondary)',
            fontSize: '12px'
        }}>
            {t('loading')}
        </div>
    ), [t]);

    const plot = (() => {
        if (methodId === 'clustered_correlation') {
            return (
                <Suspense fallback={chartFallback}>
                    <ClusteredHeatmap data={result} width={860} height={560} />
                </Suspense>
            );
        }

        if (methodId === 'mixed_effects') {
            return (
                <Suspense fallback={chartFallback}>
                    <InteractionPlot data={result} width={860} height={380} />
                </Suspense>
            );
        }

        return (
            <Suspense fallback={chartFallback}>
                <VisualizePlot
                    data={result.plot_data || []}
                    stats={result.plot_stats}
                    groups={result.groups}
                    comparisons={result?.comparisons || result?.pairwise_comparisons || result?.plot_comparisons}
                    exportScopeId={stepId}
                    exportKey="main"
                />
            </Suspense>
        );
    })();

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)]">
                <div className={`p-2 rounded-[2px] border ${result.significant ? 'bg-[color:var(--accent)] text-[color:var(--white)] border-[color:var(--accent)]' : 'bg-[color:var(--white)] text-[color:var(--text-primary)] border-[color:var(--border-color)]'}`}>
                    <BeakerIcon className="w-6 h-6" />
                </div>
                <div>
                    <h4 className="text-lg font-semibold text-[color:var(--text-primary)]">{result.method?.name || t('test_result')}</h4>
                    <p className="text-sm text-[color:var(--text-secondary)]">
                        {result.significant ? t('significant_difference_found') : t('no_significant_difference')}
                    </p>
                    {methodRequested && methodUsed && methodRequested !== methodUsed && (
                        <div className="mt-2 inline-flex items-center rounded-[2px] border border-[color:var(--accent)] bg-[color:var(--white)] px-2 py-0.5 text-xs font-medium text-[color:var(--text-primary)]">
                            {t('auto_fallback_used', { from: methodRequested, to: methodUsed })}
                        </div>
                    )}
                </div>
                <div className="ml-auto text-right">
                    <StatTooltip term="p_value" level={educationLevel} position="left">
                        <div className="text-2xl font-bold text-[color:var(--accent)]">
                            {t('p_value_short', { value: typeof result?.p_value === 'number' ? result.p_value.toFixed(4) : t('not_available') })}
                        </div>
                        <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('p_value')}</div>
                    </StatTooltip>
                </div>
            </div>

            {(assumptions && (assumptions.normality || assumptions.homogeneity)) && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                    <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('assumption_checks')}</div>
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                        {assumptions?.normality && (
                            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-3">
                                <div className="text-xs font-semibold text-[color:var(--text-primary)]">{t('normality')}</div>
                                <div className="mt-2 space-y-1">
                                    {Object.entries(assumptions.normality).map(([group, info]) => (
                                        (() => {
                                            const status = info?.passed === true ? 'passed' : (info?.passed === false ? 'failed' : 'unknown');
                                            const statusClass = status === 'passed'
                                                ? 'text-[color:var(--text-primary)]'
                                                : (status === 'failed' ? 'text-[color:var(--accent)]' : 'text-[color:var(--text-secondary)]');
                                            const statusLabel = status === 'passed' ? t('passed') : (status === 'failed' ? t('failed') : t('unknown'));
                                            return (
                                        <div key={group} className="flex items-center justify-between text-xs">
                                            <div className="text-[color:var(--text-secondary)]">{group}</div>
                                            <div className="font-mono text-[color:var(--text-primary)]">
                                                p={typeof info?.p_value === 'number' ? info.p_value.toFixed(4) : '-'}
                                                {' '}
                                                <span className={statusClass}>
                                                    {statusLabel}
                                                </span>
                                            </div>
                                        </div>
                                            );
                                        })()
                                    ))}
                                </div>
                            </div>
                        )}

                        {assumptions?.homogeneity && (
                            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-3">
                                <div className="text-xs font-semibold text-[color:var(--text-primary)]">{t('homogeneity')}</div>
                                <div className="mt-2 flex items-center justify-between text-xs">
                                    <div className="text-[color:var(--text-secondary)]">Levene</div>
                                    <div className="font-mono text-[color:var(--text-primary)]">
                                        p={typeof assumptions.homogeneity?.p_value === 'number' ? assumptions.homogeneity.p_value.toFixed(4) : '-'}
                                        {' '}
                                        <span className={assumptions.homogeneity?.passed === true ? 'text-[color:var(--text-primary)]' : (assumptions.homogeneity?.passed === false ? 'text-[color:var(--accent)]' : 'text-[color:var(--text-secondary)]')}>
                                            {assumptions.homogeneity?.passed === true ? t('passed') : (assumptions.homogeneity?.passed === false ? t('failed') : t('unknown'))}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {warnings.length > 0 && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                    <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('warnings')}</div>
                    <div className="mt-2 space-y-1">
                        {warnings.map((w, idx) => (
                            <div key={idx} className="text-sm text-[color:var(--text-primary)]">
                                {String(w)}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {(result?.ai_interpretation || result?.conclusion) && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">
                        {t('ai_interpretation')}
                    </div>
                    <div className="mt-3 border-l-2 border-[color:var(--accent)] pl-4 py-2 bg-[color:var(--bg-secondary)]">
                        <div className="text-sm text-[color:var(--text-primary)]">
                            {String(result?.ai_interpretation || result?.conclusion)}
                        </div>
                    </div>
                </div>
            )}

            {roc?.plot_data && Array.isArray(roc.plot_data) && roc.plot_data.length > 0 && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)] overflow-x-auto">
                    <div className="flex items-end justify-between gap-3">
                        <div>
                            <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('roc_curve')}</div>
                            {typeof roc?.auc === 'number' && (
                                <div className="mt-1 text-sm font-mono text-[color:var(--text-primary)]">{t('roc_auc', { value: roc.auc.toFixed(3) })}</div>
                            )}
                        </div>
                    </div>
                    <div className="mt-3">
                        <Suspense fallback={chartFallback}>
                            <VisualizePlot data={roc.plot_data} />
                        </Suspense>
                    </div>
                </div>
            )}

            {coefficients.length > 0 && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)] overflow-x-auto">
                    <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('coefficients')}</div>
                    <table className="mt-3 min-w-full divide-y divide-[color:var(--border-color)]">
                        <thead className="bg-[color:var(--bg-secondary)]">
                            <tr>
                                <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('variable')}</th>
                                <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('beta')}</th>
                                <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('p_value')}</th>
                                <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('confidence_interval')}</th>
                                {coefficients.some(c => typeof c?.odds_ratio === 'number') && (
                                    <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('odds_ratio')}</th>
                                )}
                            </tr>
                        </thead>
                        <tbody className="bg-[color:var(--white)] divide-y divide-[color:var(--border-color)]">
                            {coefficients.map((c, idx) => {
                                const ciText = (typeof c?.ci_lower === 'number' && typeof c?.ci_upper === 'number')
                                    ? `[${c.ci_lower.toFixed(3)}, ${c.ci_upper.toFixed(3)}]`
                                    : '-';
                                const orText = (typeof c?.odds_ratio === 'number' && typeof c?.or_ci_lower === 'number' && typeof c?.or_ci_upper === 'number')
                                    ? `${c.odds_ratio.toFixed(3)} [${c.or_ci_lower.toFixed(3)}, ${c.or_ci_upper.toFixed(3)}]`
                                    : (typeof c?.odds_ratio === 'number' ? c.odds_ratio.toFixed(3) : '-');
                                return (
                                    <tr key={idx}>
                                        <td className="px-4 py-2 text-sm text-[color:var(--text-primary)] font-mono">{String(c?.variable ?? '')}</td>
                                        <td className="px-4 py-2 text-sm text-[color:var(--text-secondary)] font-mono">{typeof c?.coefficient === 'number' ? c.coefficient.toFixed(3) : '-'}</td>
                                        <td className="px-4 py-2 text-sm text-[color:var(--text-secondary)] font-mono">{typeof c?.p_value === 'number' ? c.p_value.toFixed(4) : '-'}</td>
                                        <td className="px-4 py-2 text-sm text-[color:var(--text-secondary)] font-mono">{ciText}</td>
                                        {coefficients.some(x => typeof x?.odds_ratio === 'number') && (
                                            <td className="px-4 py-2 text-sm text-[color:var(--text-secondary)] font-mono">{orText}</td>
                                        )}
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Effect Size with Visual Explainer */}
            {typeof result?.effect_size === 'number' && (
                <EffectSizeExplainer
                    type={result.effect_size_name === "Cohen's d" ? 'cohens_d' :
                        result.effect_size_name === 'η²' ? 'eta_squared' :
                            result.effect_size_name === 'r' ? 'r' : 'cohens_d'}
                    value={result.effect_size}
                    ci={typeof result.effect_size_ci_lower === 'number' && typeof result.effect_size_ci_upper === 'number'
                        ? [result.effect_size_ci_lower, result.effect_size_ci_upper]
                        : undefined}
                />
            )}

            {/* Power with Recommendations */}
            {typeof result?.power === 'number' && (
                <PowerExplainer
                    power={result.power}
                    effectSize={typeof result?.effect_size === 'number' ? result.effect_size : undefined}
                />
            )}

            {/* Additional Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {(deltaWide || deltaPlot) && (
                    <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                        <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">Δ</div>
                        {deltaWide ? (
                            <div className="mt-1 text-lg font-mono font-bold text-[color:var(--text-primary)]">
                                {typeof deltaWide?.delta_abs_mean === 'number' ? formatNum(deltaWide.delta_abs_mean, 2) : '—'}
                                {typeof deltaWide?.delta_pct_mean === 'number' ? ` (${formatNum(deltaWide.delta_pct_mean, 1)}%)` : ''}
                            </div>
                        ) : (
                            <div className="mt-1 text-lg font-mono font-bold text-[color:var(--text-primary)]">
                                {deltaPlot ? formatNum(deltaPlot.delta_abs, 2) : '—'}
                                {deltaPlot && typeof deltaPlot.delta_pct === 'number' ? ` (${formatNum(deltaPlot.delta_pct, 1)}%)` : ''}
                            </div>
                        )}
                        <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                            {deltaWide?.effect_size_interpretation?.label_ru
                                ? `эффект: ${String(deltaWide.effect_size_interpretation.label_ru)}`
                                : (result?.effect_size_interpretation?.label_ru ? `эффект: ${String(result.effect_size_interpretation.label_ru)}` : '')}
                        </div>
                    </div>
                )}

                {/* Effect Size Compact (fallback if no visual explainer) */}
                {typeof result?.effect_size !== 'number' && (
                    <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                        <StatTooltip term="effect_size">
                            <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('effect_size')}</div>
                        </StatTooltip>
                        <div className="mt-1 text-lg font-mono font-bold text-[color:var(--text-primary)]">
                            {t('not_available_short')}
                        </div>
                    </div>
                )}

                {/* Power Compact (fallback if no visual explainer) */}
                {typeof result?.power !== 'number' && (
                    <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                        <StatTooltip term="power">
                            <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('power')}</div>
                        </StatTooltip>
                        <div className="mt-1 text-lg font-mono font-bold text-[color:var(--text-primary)]">
                            {t('not_available_short')}
                        </div>
                    </div>
                )}

                {/* BF10 */}
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                    <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('bf10')}</div>
                    <div className="mt-1 text-lg font-mono font-bold text-[color:var(--text-primary)]">
                        {typeof result?.bf10 === 'number' ? result.bf10.toPrecision(3) : t('not_available_short')}
                    </div>
                    {typeof result?.bf10 === 'number' && Number.isFinite(result.bf10) && (
                        <div className="flex items-center gap-2 mt-2">
                            <span className="text-sm text-[color:var(--text-secondary)]">Bayes Factor (BF₁₀):</span>
                            <span className="font-mono font-semibold">{Number(result.bf10).toFixed(2)}</span>
                            <span
                                className={`text-xs px-2 py-0.5 rounded ${
                                    result.bf10 > 100
                                        ? 'bg-green-100 text-green-800'
                                        : result.bf10 > 10
                                            ? 'bg-green-50 text-green-700'
                                            : result.bf10 > 3
                                                ? 'bg-yellow-50 text-yellow-700'
                                                : result.bf10 > 1
                                                    ? 'bg-gray-100 text-gray-600'
                                                    : 'bg-red-50 text-red-700'
                                }`}
                            >
                                {result.bf10 > 100
                                    ? 'очень сильные'
                                    : result.bf10 > 10
                                        ? 'сильные'
                                        : result.bf10 > 3
                                            ? 'умеренные'
                                            : result.bf10 > 1
                                                ? 'слабые'
                                                : 'против H₁'}
                                {' '}доказательства
                            </span>
                        </div>
                    )}
                </div>
            </div>

            <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)] overflow-x-auto">
                {plot}
            </div>
        </div>
    );
};

/* --- MAIN DASHBOARD --- */
const StepResults = ({ runId, datasetId, mode = 'results' }) => {
    const { t, hasTranslation } = useTranslation();
    const navigate = useNavigate();
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState(0);
    const [sectionOrder, setSectionOrder] = useState([]);
    const [sectionEnabled, setSectionEnabled] = useState({});
    const reportPrefsKey = 'statproject_report_prefs_v1';
    const readReportPrefs = () => {
        try {
            const raw = localStorage.getItem(reportPrefsKey);
            const parsed = raw ? JSON.parse(raw) : null;
            return parsed && typeof parsed === 'object' ? parsed : {};
        } catch {
            return {};
        }
    };
    const initialReportPrefs = readReportPrefs();

    const [reportFormat, setReportFormat] = useState(() => String(initialReportPrefs?.format || 'docx'));
    const [reportStyle, setReportStyle] = useState(() => String(initialReportPrefs?.style || 'apa7'));
    const [reportDensity, setReportDensity] = useState(() => String(initialReportPrefs?.density || 'comfortable'));
    const [reportAccent, setReportAccent] = useState(() => String(initialReportPrefs?.accent || ''));

    const recentRunsKey = 'statproject_recent_runs_v1';
    const makeModeHref = (targetMode) => `/${targetMode}/${datasetId}?run=${encodeURIComponent(String(runId))}`;

    const recentRuns = (() => {
        try {
            const raw = localStorage.getItem(recentRunsKey);
            const parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? parsed : [];
        } catch {
            return [];
        }
    })();

    useEffect(() => {
        if (!runId || !datasetId) return;
        let cancelled = false;

        queueMicrotask(() => {
            if (cancelled) return;
            setLoading(true);
        });

        getAnalysisResults(datasetId, runId)
            .then((data) => {
                if (cancelled) return;
                setResults(data);
            })
            .catch(console.error)
            .finally(() => {
                if (cancelled) return;
                setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [runId, datasetId]);

    useEffect(() => {
        if (!results || !datasetId || !runId) return;
        const entry = {
            datasetId: String(datasetId),
            runId: String(runId),
            protocolName: String(results.protocol_name || results.protocolName || ''),
            ts: Date.now(),
        };

        try {
            const raw = localStorage.getItem(recentRunsKey);
            const parsed = raw ? JSON.parse(raw) : [];
            const prev = Array.isArray(parsed) ? parsed : [];
            const deduped = [entry, ...prev.filter((r) => !(String(r?.datasetId) === entry.datasetId && String(r?.runId) === entry.runId))]
                .slice(0, 20);
            localStorage.setItem(recentRunsKey, JSON.stringify(deduped));
        } catch {
            return;
        }
    }, [datasetId, results, runId]);

    useEffect(() => {
        try {
            localStorage.setItem(
                reportPrefsKey,
                JSON.stringify({
                    format: reportFormat,
                    style: reportStyle,
                    density: reportDensity,
                    accent: reportAccent,
                })
            );
        } catch {
            return;
        }
    }, [reportAccent, reportDensity, reportFormat, reportStyle]);

    const baseSteps = useMemo(() => {
        const irBlocks = Array.isArray(results?.result_ir?.blocks) ? results.result_ir.blocks : null;
        if (irBlocks && irBlocks.length) {
            return irBlocks
                .map((b) => {
                    if (!b || typeof b !== 'object') return null;
                    const key = String(b.id || '').trim();
                    if (!key) return null;
                    const i18nKey = `step_${key}`;
                    const fallback = String(b.title || '').trim() || key.replace(/_/g, ' ').toUpperCase();
                    const label = hasTranslation(i18nKey) ? t(i18nKey) : fallback;
                    return {
                        id: key,
                        data: b.payload,
                        label,
                    };
                })
                .filter(Boolean);
        }

        const map = results?.results && typeof results.results === 'object' ? results.results : {};
        return Object.keys(map).map((key) => {
            const i18nKey = `step_${key}`;
            const label = hasTranslation(i18nKey) ? t(i18nKey) : key.replace(/_/g, ' ').toUpperCase();
            return {
                id: key,
                data: map[key],
                label,
            };
        });
    }, [hasTranslation, results, t]);

    const baseStepIds = useMemo(() => baseSteps.map((s) => s.id), [baseSteps]);

    const mergedSectionOrder = useMemo(() => {
        const prevSafe = Array.isArray(sectionOrder) ? sectionOrder : [];
        const preserved = prevSafe.filter((id) => baseStepIds.includes(id));
        const appended = baseStepIds.filter((id) => !preserved.includes(id));
        return preserved.length || appended.length ? [...preserved, ...appended] : [];
    }, [baseStepIds, sectionOrder]);

    const mergedSectionEnabled = useMemo(() => {
        const src = (sectionEnabled && typeof sectionEnabled === 'object') ? sectionEnabled : {};
        const out = {};
        baseStepIds.forEach((id) => {
            const v = src[id];
            out[id] = typeof v === 'boolean' ? v : true;
        });
        return out;
    }, [baseStepIds, sectionEnabled]);

    const stepsById = useMemo(() => {
        const map = new Map();
        baseSteps.forEach((s) => map.set(s.id, s));
        return map;
    }, [baseSteps]);

    const orderedSteps = useMemo(() => {
        const order = mergedSectionOrder;
        const stitched = order.map((id) => stepsById.get(id)).filter(Boolean);
        const extras = baseSteps.filter((s) => !order.includes(s.id));
        return [...stitched, ...extras];
    }, [baseSteps, mergedSectionOrder, stepsById]);

    const visibleSteps = useMemo(() => {
        return orderedSteps.filter((s) => mergedSectionEnabled?.[s.id] !== false);
    }, [mergedSectionEnabled, orderedSteps]);

    const safeActiveTab = Math.max(0, Math.min(activeTab, Math.max(0, visibleSteps.length - 1)));
    const activeStep = visibleSteps[safeActiveTab];

    const reportParams = useMemo(() => {
        return {
            style: reportStyle,
            density: reportDensity,
            accent: reportAccent || undefined,
            sections: visibleSteps.map((s) => s.id),
            order: mergedSectionOrder,
        };
    }, [mergedSectionOrder, reportAccent, reportDensity, reportStyle, visibleSteps]);

    const reportHtmlUrl = useMemo(() => {
        return getProtocolReportUrl(datasetId, runId, 'html', reportParams);
    }, [datasetId, reportParams, runId]);

    const handleDownloadReport = async () => {
        try {
            const fmt = String(reportFormat || 'pdf').toLowerCase();
            const filename = `protocol_report_${runId}.${fmt}`;
            const data = await downloadProtocolReport(datasetId, runId, fmt, reportParams);
            const blob = typeof data === 'string'
                ? new Blob([data], { type: 'text/html;charset=utf-8' })
                : data;
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch {
            alert('Не удалось скачать отчёт');
        }
    };

    const moveSection = (id, direction) => {
        setSectionOrder((prev) => {
            const prevSafe = Array.isArray(prev) ? prev : [];
            const preserved = prevSafe.filter((k) => baseStepIds.includes(k));
            const appended = baseStepIds.filter((k) => !preserved.includes(k));
            const order = [...preserved, ...appended];
            const idx = order.indexOf(id);
            if (idx < 0) return prev;
            const nextIdx = idx + direction;
            if (nextIdx < 0 || nextIdx >= order.length) return prev;
            const tmp = order[idx];
            order[idx] = order[nextIdx];
            order[nextIdx] = tmp;
            return order;
        });
    };

    if (loading) return <div className="p-10 text-center animate-pulse text-[color:var(--text-secondary)]">{t('loading_results')}</div>;
    if (!results) return <div className="p-10 text-center text-[color:var(--error)]">{t('failed_to_load_results')}</div>;

    return (
        <div className="animate-fadeIn min-h-screen pb-20">
            {/* Header */}
            <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4 mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-[color:var(--text-primary)]">{results.protocol_name}</h2>
                    <p className="text-[color:var(--text-secondary)] text-sm">{t('run_id')}: {runId}</p>
                    <div className="mt-3 flex items-center gap-2 flex-wrap">
                        <Button
                            variant={mode === 'results' ? 'secondary' : 'ghost'}
                            size="sm"
                            onClick={() => navigate(makeModeHref('results'))}
                        >
                            Результаты
                        </Button>
                        <Button
                            variant={mode === 'graphs' ? 'secondary' : 'ghost'}
                            size="sm"
                            onClick={() => navigate(makeModeHref('graphs'))}
                        >
                            Графики
                        </Button>
                        <Button
                            variant={mode === 'report' ? 'secondary' : 'ghost'}
                            size="sm"
                            onClick={() => navigate(makeModeHref('report'))}
                        >
                            Протокол
                        </Button>
                        <div className="h-8 w-px bg-[color:var(--border-color)]" />
                        <div className="text-xs text-[color:var(--text-secondary)]">
                            <span className="font-mono">/results/{datasetId}?run=</span>
                            <span className="font-mono font-semibold text-[color:var(--text-primary)]">{runId}</span>
                        </div>
                    </div>
                </div>
                <div className="w-full lg:w-[520px] rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                    <div className="px-4 py-3 border-b border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex flex-wrap items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-[color:var(--text-primary)]">📄 Отчёт</div>
                        <div className="flex items-center gap-2">
                            <select
                                value={reportFormat}
                                onChange={(e) => setReportFormat(e.target.value)}
                                className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                                aria-label="Формат отчёта"
                            >
                                <option value="docx">DOCX</option>
                                <option value="pdf">PDF</option>
                                <option value="html">HTML</option>
                            </select>
                            <select
                                value={reportStyle}
                                onChange={(e) => setReportStyle(e.target.value)}
                                className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                                aria-label="Стиль отчёта"
                            >
                                <option value="apa7">APA 7</option>
                                <option value="gost">ГОСТ</option>
                                <option value="simple">Простой</option>
                                <option value="editorial">Редакционный</option>
                                <option value="brutal">Брутал</option>
                            </select>
                            <select
                                value={reportDensity}
                                onChange={(e) => setReportDensity(e.target.value)}
                                className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                                aria-label="Плотность отчёта"
                            >
                                <option value="compact">Плотно</option>
                                <option value="comfortable">Комфортно</option>
                                <option value="spacious">Просторно</option>
                            </select>
                            <select
                                value={reportAccent}
                                onChange={(e) => setReportAccent(e.target.value)}
                                className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                                aria-label="Акцент"
                            >
                                <option value="">Акцент: авто</option>
                                <option value="#111111">Акцент: чёрный</option>
                                <option value="#3498db">Акцент: синий</option>
                                <option value="#ff2d55">Акцент: фуксия</option>
                                <option value="#a3ff12">Акцент: лайм</option>
                            </select>
                            <Button variant="ghost" size="sm" onClick={() => window.open(reportHtmlUrl, '_blank')}>
                                👁 Превью
                            </Button>
                            <Button variant="secondary" size="sm" onClick={handleDownloadReport}>
                                <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                                Скачать
                            </Button>
                        </div>
                    </div>

                    <div className="p-3">
                        {Array.isArray(recentRuns) && recentRuns.length > 1 && (
                            <div className="mb-3 flex items-center gap-2">
                                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Недавние</div>
                                <select
                                    className="h-8 flex-1 min-w-0 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                                    value={`${datasetId}__${runId}`}
                                    onChange={(e) => {
                                        const value = e.target.value;
                                        const [ds, run] = String(value).split('__');
                                        if (!ds || !run) return;
                                        navigate(`/${mode}/${ds}?run=${encodeURIComponent(run)}`);
                                    }}
                                    aria-label="Недавние запуски"
                                >
                                    {recentRuns
                                        .filter((r) => String(r?.datasetId) === String(datasetId))
                                        .map((r) => (
                                            <option key={`${String(r?.datasetId)}__${String(r?.runId)}`} value={`${String(r?.datasetId)}__${String(r?.runId)}`}>
                                                {String(r?.protocolName || 'Run')} · {String(r?.runId).slice(0, 8)}
                                            </option>
                                        ))}
                                </select>
                            </div>
                        )}
                        <div className="grid grid-cols-1 gap-1">
                            {orderedSteps.map((s, idx) => (
                                <div key={s.id} className="flex items-center justify-between gap-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2">
                                    <label className="flex items-center gap-3 min-w-0 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={mergedSectionEnabled?.[s.id] !== false}
                                            onChange={() => setSectionEnabled((prev) => ({
                                                ...(prev && typeof prev === 'object' ? prev : {}),
                                                [s.id]: !(prev?.[s.id] !== false)
                                            }))}
                                            className="h-4 w-4 accent-[color:var(--accent)]"
                                        />
                                        <span className="text-sm text-[color:var(--text-primary)] truncate">{s.label}</span>
                                    </label>
                                    <div className="flex items-center gap-1">
                                        <button
                                            type="button"
                                            onClick={() => moveSection(s.id, -1)}
                                            disabled={idx === 0}
                                            className="h-7 w-7 inline-flex items-center justify-center rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-secondary)] disabled:opacity-40"
                                            aria-label="Поднять секцию"
                                        >
                                            ↑
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => moveSection(s.id, 1)}
                                            disabled={idx === orderedSteps.length - 1}
                                            className="h-7 w-7 inline-flex items-center justify-center rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-secondary)] disabled:opacity-40"
                                            aria-label="Опустить секцию"
                                        >
                                            ↓
                                        </button>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => {
                                                window.dispatchEvent(
                                                    new CustomEvent('statproject:export-plot', { detail: { scopeId: s.id, key: 'main' } })
                                                );
                                            }}
                                        >
                                            <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                                            {t('export_plot')}
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {mode === 'report' ? (
                <div className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden">
                    <div className="px-6 py-4 border-b border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex items-center justify-between gap-3 flex-wrap">
                        <div>
                            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Итоговый протокол</div>
                            <div className="mt-1 text-sm text-[color:var(--text-secondary)]">Превью отчёта, который можно экспортировать в DOCX/PDF.</div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button variant="ghost" size="sm" onClick={() => window.open(reportHtmlUrl, '_blank')}>Открыть в новой вкладке</Button>
                            <Button variant="secondary" size="sm" onClick={handleDownloadReport}>Скачать</Button>
                        </div>
                    </div>
                    <iframe title="report" src={reportHtmlUrl} className="w-full" style={{ height: '72vh', border: 0 }} />
                </div>
            ) : mode === 'graphs' ? (
                <div className="space-y-6">
                    {visibleSteps
                        .filter((s) => {
                            const d = s?.data;
                            if (!d || typeof d !== 'object') return false;
                            if (Array.isArray(d?.plot_data) && d.plot_data.length > 0) return true;
                            if (d?.roc && Array.isArray(d.roc.plot_data) && d.roc.plot_data.length > 0) return true;
                            if (d?.type === 'clustered_correlation' || d?.method?.id === 'clustered_correlation') return true;
                            if (d?.type === 'mixed_effects' || d?.method?.id === 'mixed_effects') return true;
                            return false;
                        })
                        .map((s) => (
                            <div key={s.id} className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-6">
                                <div className="flex items-center justify-between gap-4 flex-wrap">
                                    <div className="text-sm font-semibold text-[color:var(--text-primary)]">{s.label}</div>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => {
                                            window.dispatchEvent(
                                                new CustomEvent('statproject:export-plot', { detail: { scopeId: s.id, key: 'main' } })
                                            );
                                        }}
                                    >
                                        <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                                        {t('export_plot')}
                                    </Button>
                                </div>
                                <div className="mt-4">
                                    {s.data?.type === 'clustered_correlation' || s.data?.method?.id === 'clustered_correlation' ? (
                                        <Suspense fallback={<div className="h-[360px] animate-pulse bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px]" />}>
                                            <ClusteredHeatmap data={s.data} width={860} height={560} />
                                        </Suspense>
                                    ) : s.data?.type === 'mixed_effects' || s.data?.method?.id === 'mixed_effects' ? (
                                        <Suspense fallback={<div className="h-[360px] animate-pulse bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px]" />}>
                                            <InteractionPlot data={s.data} width={860} height={380} />
                                        </Suspense>
                                    ) : (
                                        <Suspense fallback={<div className="h-[360px] animate-pulse bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px]" />}>
                                            <VisualizePlot
                                                data={s.data?.plot_data || []}
                                                stats={s.data?.plot_stats}
                                                groups={s.data?.groups}
                                                comparisons={s.data?.comparisons || s.data?.pairwise_comparisons || s.data?.plot_comparisons}
                                                exportScopeId={s.id}
                                                exportKey="main"
                                            />
                                        </Suspense>
                                    )}
                                </div>
                            </div>
                        ))}

                    {visibleSteps.length === 0 && (
                        <div className="p-6 text-sm text-[color:var(--text-secondary)]">Нет секций с графиками.</div>
                    )}
                </div>
            ) : (
                <>
                    {/* Tabs */}
                    <div className="border-b border-[color:var(--border-color)] mb-6">
                        <nav className="-mb-px flex space-x-8">
                            {visibleSteps.map((step, idx) => (
                                <button
                                    key={step.id}
                                    onClick={() => setActiveTab(idx)}
                                    className={`
                                        py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap transition-colors
                                        ${safeActiveTab === idx
                                            ? 'border-[color:var(--accent)] text-[color:var(--accent)]'
                                            : 'border-transparent text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--border-color)]'}
                                    `}
                                >
                                    {step.label}
                                </button>
                            ))}
                        </nav>
                    </div>

                    {/* Content Body */}
                    <div className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-6">
                        {!activeStep ? (
                            <div className="text-sm text-[color:var(--text-secondary)]">Нет выбранных секций отчёта</div>
                        ) : (
                            <>
                                {activeStep.data.type === 'table_1' && (
                                    <Table1View data={activeStep.data} />
                                )}

                                {(activeStep.data.p_value !== undefined) && (
                                    <CompareView result={activeStep.data} stepId={activeStep.id} />
                                )}

                                {activeStep.data.error && (
                                    <div className="text-[color:var(--error)] p-4 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)]">
                                        {t('analysis_error')}: {activeStep.data.error}
                                    </div>
                                )}

                                {!['table_1'].includes(activeStep.data.type) && activeStep.data.p_value === undefined && (
                                    <pre className="text-xs bg-[color:var(--bg-secondary)] p-4 rounded-[2px] border border-[color:var(--border-color)] overflow-auto max-h-96">
                                        {JSON.stringify(activeStep.data, null, 2)}
                                    </pre>
                                )}
                            </>
                        )}
                    </div>
                </>
            )}
        </div>
    );
};

export default StepResults;
