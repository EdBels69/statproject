/**
 * StudyDAG — интерактивная DAG-диаграмма дизайна исследования.
 *
 * Теперь можно:
 *  - Назначать переменные в роли прямо из DAG (dropdown-ы)
 *  - Шаблоны дизайна подставляют первые подходящие колонки
 *  - Убирать переменные из ролей кликом на ×
 *  - Узлы можно перетаскивать
 *
 * Props:
 *   roles         : { target, group, covariates: string[] }
 *   onRolesChange : (next) => void
 *   columns       : Array<{ name, uiType }>
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    ReactFlow,
    Background,
    Controls,
    MarkerType,
    addEdge,
    useEdgesState,
    useNodesState,
    Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// ── Стили ─────────────────────────────────────────────────────────────────────
const cls = {
    btn:    'px-2.5 py-1 text-xs font-semibold rounded-[2px] border transition-colors',
    btnOn:  'bg-[color:var(--accent)] text-white border-[color:var(--accent)]',
    btnOff: 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:bg-[color:var(--bg-secondary)]',
    select: 'px-2 py-1 text-xs rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-primary)] outline-none',
    label:  'text-[11px] font-semibold text-[color:var(--text-muted)] uppercase tracking-[0.12em]',
    pill:   'inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-[2px] border',
    x:      'cursor-pointer opacity-50 hover:opacity-100 text-[10px] font-bold',
};

// ── Шаблоны дизайнов ──────────────────────────────────────────────────────────
const TEMPLATES = [
    { id: 'rct',             label: 'РКИ',            desc: 'Лечение → Исход + ковариаты',   needsGroup: true,  covCount: 2 },
    { id: 'cohort',          label: 'Когорта',        desc: 'Экспозиция → Исход + время',     needsGroup: true,  covCount: 3 },
    { id: 'case_control',    label: 'Случай-контроль',desc: 'Факторы риска → Исход',           needsGroup: true,  covCount: 2 },
    { id: 'cross_sectional', label: 'Поперечное',     desc: 'Переменная X ↔ Y',               needsGroup: true,  covCount: 0 },
];

// ── Конфиг цветов узлов ───────────────────────────────────────────────────────
const NODE_STYLES = {
    outcome:   { background: '#d1fae5', border: '2px solid #10b981', color: '#065f46', fontWeight: 700 },
    predictor: { background: '#dbeafe', border: '2px solid #3b82f6', color: '#1e40af', fontWeight: 700 },
    covariate: { background: '#f3f4f6', border: '1px solid #9ca3af', color: '#374151', fontWeight: 500 },
};

const EDGE_MAIN = { stroke: '#3b82f6', strokeWidth: 2 };
const EDGE_COV  = { stroke: '#9ca3af', strokeWidth: 1.5, strokeDasharray: '4 3' };

// ── roles → nodes + edges ─────────────────────────────────────────────────────
function rolesToFlow(roles) {
    const nodes = [];
    const edges = [];
    const covs = Array.isArray(roles.covariates) ? roles.covariates : [];
    const totalCovs = covs.length;

    if (roles.target) {
        nodes.push({
            id: 'outcome',
            position: { x: 400, y: 100 },
            data: { label: `🎯 ${roles.target}`, role: 'outcome' },
            style: { ...NODE_STYLES.outcome, borderRadius: 4, padding: '8px 16px', fontSize: 13, minWidth: 120, textAlign: 'center' },
        });
    }

    if (roles.group) {
        nodes.push({
            id: 'predictor',
            position: { x: 60, y: 100 },
            data: { label: `📊 ${roles.group}`, role: 'predictor' },
            style: { ...NODE_STYLES.predictor, borderRadius: 4, padding: '8px 16px', fontSize: 13, minWidth: 120, textAlign: 'center' },
        });
        if (roles.target) {
            edges.push({
                id: 'e-pred-out', source: 'predictor', target: 'outcome',
                markerEnd: { type: MarkerType.ArrowClosed, color: '#3b82f6' },
                style: EDGE_MAIN,
                label: 'основная гипотеза',
                labelStyle: { fontSize: 10, fill: '#6b7280' },
                labelBgStyle: { fill: 'transparent' },
            });
        }
    }

    covs.forEach((cov, i) => {
        const id = `cov_${i}`;
        // Располагаем ковариаты полукругом внизу
        const spread = Math.min(totalCovs * 140, 500);
        const startX = 230 - spread / 2;
        nodes.push({
            id,
            position: { x: startX + i * 140, y: 240 },
            data: { label: cov, role: 'covariate' },
            style: { ...NODE_STYLES.covariate, borderRadius: 4, padding: '6px 12px', fontSize: 12, minWidth: 90, textAlign: 'center' },
        });
        if (roles.target) {
            edges.push({
                id: `e-cov-${i}`, source: id, target: 'outcome',
                markerEnd: { type: MarkerType.ArrowClosed, color: '#9ca3af' },
                style: EDGE_COV,
            });
        }
    });

    return { nodes, edges };
}

// ── Легенда ─────────────────────────────────────────────────────────────────
const Legend = () => (
    <div className="flex items-center gap-4 text-[11px] text-[color:var(--text-secondary)]">
        {[
            { color: '#10b981', bg: '#d1fae5', label: 'Исход' },
            { color: '#3b82f6', bg: '#dbeafe', label: 'Предиктор' },
            { color: '#9ca3af', bg: '#f3f4f6', label: 'Ковариата' },
        ].map(({ color, bg, label }) => (
            <span key={label} className="flex items-center gap-1">
                <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 2, background: bg, border: `1.5px solid ${color}` }} />
                {label}
            </span>
        ))}
    </div>
);

// ── Пустое состояние ────────────────────────────────────────────────────────
const EmptyDAG = () => (
    <div className="flex flex-col items-center justify-center h-full text-center gap-2 opacity-60">
        <div className="text-2xl">○ → ○</div>
        <div className="text-xs font-semibold text-[color:var(--text-secondary)]">
            Выбери исход и предиктор ниже — диаграмма появится
        </div>
    </div>
);

// ── Главный компонент ───────────────────────────────────────────────────────
const StudyDAG = ({ roles, onRolesChange, columns }) => {
    const [activeTemplate, setActiveTemplate] = useState(null);

    const safeRoles = roles || { target: '', group: '', covariates: [] };
    const { nodes: initNodes, edges: initEdges } = useMemo(() => rolesToFlow(safeRoles), [safeRoles]);

    const [nodes, setNodes, onNodesChange] = useNodesState(initNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges);

    useEffect(() => {
        const { nodes: n, edges: e } = rolesToFlow(safeRoles);
        setNodes(n);
        setEdges(e);
    }, [safeRoles, setNodes, setEdges]);

    const onConnect = useCallback(
        (params) => setEdges((eds) => addEdge(params, eds)),
        [setEdges]
    );

    const isEmpty = !safeRoles.target && !safeRoles.group;

    // Колонки, ещё не назначенные ни в какую роль
    const colNames = useMemo(() => columns.map(c => c.name || c), [columns]);
    const usedNames = useMemo(() => {
        const s = new Set();
        if (safeRoles.target) s.add(safeRoles.target);
        if (safeRoles.group) s.add(safeRoles.group);
        (safeRoles.covariates || []).forEach(c => s.add(c));
        return s;
    }, [safeRoles]);
    const availableCols = useMemo(() => colNames.filter(n => !usedNames.has(n)), [colNames, usedNames]);

    // ── Хендлеры назначения ролей ──────────────────────────────────────────
    const setTarget = useCallback((col) => {
        if (!col) return;
        onRolesChange({ ...safeRoles, target: col });
    }, [safeRoles, onRolesChange]);

    const setGroup = useCallback((col) => {
        if (!col) return;
        onRolesChange({ ...safeRoles, group: col });
    }, [safeRoles, onRolesChange]);

    const addCovariate = useCallback((col) => {
        if (!col) return;
        const covs = [...(safeRoles.covariates || [])];
        if (!covs.includes(col)) covs.push(col);
        onRolesChange({ ...safeRoles, covariates: covs });
    }, [safeRoles, onRolesChange]);

    const removeTarget = useCallback(() => {
        onRolesChange({ ...safeRoles, target: '' });
    }, [safeRoles, onRolesChange]);

    const removeGroup = useCallback(() => {
        onRolesChange({ ...safeRoles, group: '' });
    }, [safeRoles, onRolesChange]);

    const removeCovariate = useCallback((col) => {
        onRolesChange({ ...safeRoles, covariates: (safeRoles.covariates || []).filter(c => c !== col) });
    }, [safeRoles, onRolesChange]);

    // ── Шаблоны: авто-подставляем первые подходящие колонки ────────────────
    const applyTemplate = useCallback((tmplId) => {
        const tmpl = TEMPLATES.find(t => t.id === tmplId);
        if (!tmpl) return;
        setActiveTemplate(tmplId);

        // Берём первые доступные колонки
        const all = [...colNames];
        const newTarget = all[0] || '';
        const newGroup = tmpl.needsGroup ? (all[1] || '') : '';
        const usedSet = new Set([newTarget, newGroup].filter(Boolean));
        const newCovs = all.filter(n => !usedSet.has(n)).slice(0, tmpl.covCount);

        onRolesChange({ target: newTarget, group: newGroup, covariates: newCovs });
    }, [colNames, onRolesChange]);

    const clearAll = useCallback(() => {
        setActiveTemplate(null);
        onRolesChange({ target: '', group: '', covariates: [] });
    }, [onRolesChange]);

    return (
        <div className="flex flex-col gap-3">
            {/* ── Шаблоны ────────────────────────────────────────────── */}
            <div className="flex flex-wrap items-center gap-1.5">
                <span className={cls.label}>Шаблон:</span>
                {TEMPLATES.map(tmpl => (
                    <button
                        key={tmpl.id}
                        onClick={() => applyTemplate(tmpl.id)}
                        title={tmpl.desc}
                        className={`${cls.btn} ${activeTemplate === tmpl.id ? cls.btnOn : cls.btnOff}`}
                    >
                        {tmpl.label}
                    </button>
                ))}
                {(safeRoles.target || safeRoles.group) && (
                    <button onClick={clearAll} className={`${cls.btn} ${cls.btnOff} text-red-500`} title="Сбросить все роли">
                        ✕ Сбросить
                    </button>
                )}
            </div>

            {/* ── Назначение ролей ────────────────────────────────────── */}
            <div className="grid grid-cols-3 gap-3">
                {/* Исход */}
                <div>
                    <div className={`${cls.label} mb-1`}>🎯 Исход (Outcome)</div>
                    {safeRoles.target ? (
                        <span className={`${cls.pill} border-green-300 bg-green-50 text-green-800`}>
                            {safeRoles.target}
                            <span className={cls.x} onClick={removeTarget}>✕</span>
                        </span>
                    ) : (
                        <select className={cls.select} value="" onChange={e => setTarget(e.target.value)}>
                            <option value="">Выбери...</option>
                            {availableCols.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                    )}
                </div>

                {/* Предиктор */}
                <div>
                    <div className={`${cls.label} mb-1`}>📊 Предиктор / Группа</div>
                    {safeRoles.group ? (
                        <span className={`${cls.pill} border-blue-300 bg-blue-50 text-blue-800`}>
                            {safeRoles.group}
                            <span className={cls.x} onClick={removeGroup}>✕</span>
                        </span>
                    ) : (
                        <select className={cls.select} value="" onChange={e => setGroup(e.target.value)}>
                            <option value="">Выбери...</option>
                            {availableCols.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                    )}
                </div>

                {/* Ковариаты */}
                <div>
                    <div className={`${cls.label} mb-1`}>Ковариаты</div>
                    <div className="flex flex-wrap gap-1 mb-1">
                        {(safeRoles.covariates || []).map(c => (
                            <span key={c} className={`${cls.pill} border-gray-300 bg-gray-50 text-gray-700`}>
                                {c}
                                <span className={cls.x} onClick={() => removeCovariate(c)}>✕</span>
                            </span>
                        ))}
                    </div>
                    {availableCols.length > 0 && (
                        <select className={cls.select} value="" onChange={e => { addCovariate(e.target.value); e.target.value = ''; }}>
                            <option value="">+ добавить...</option>
                            {availableCols.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                    )}
                </div>
            </div>

            {/* ── DAG граф ───────────────────────────────────────────── */}
            <div
                style={{ height: 280, borderRadius: 4, border: '1px solid var(--border-color)', overflow: 'hidden' }}
                className="bg-[color:var(--white)]"
            >
                {isEmpty ? (
                    <EmptyDAG />
                ) : (
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        fitView
                        fitViewOptions={{ padding: 0.3 }}
                        minZoom={0.4}
                        proOptions={{ hideAttribution: true }}
                    >
                        <Background gap={16} color="#f0f0f0" />
                        <Controls showInteractive={false} />
                        <Panel position="bottom-right">
                            <Legend />
                        </Panel>
                    </ReactFlow>
                )}
            </div>

            <div className="text-[11px] text-[color:var(--text-muted)]">
                Назначай роли выше — диаграмма обновляется автоматически. Узлы можно перетаскивать.
            </div>
        </div>
    );
};

export default StudyDAG;
