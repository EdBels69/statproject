/**
 * StudyDAG — интерактивная DAG-диаграмма дизайна исследования.
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

// ── Шаблоны дизайнов ──────────────────────────────────────────────────────────
const TEMPLATES = [
    {
        id: 'rct',
        label: 'РКИ',
        desc: 'Randomized Controlled Trial',
        hint: 'Лечение → Исход + ковариаты',
        targetHint: 'Исход (Outcome)',
        groupHint: 'Группа лечения',
        covHints: ['Возраст', 'Пол'],
    },
    {
        id: 'cohort',
        label: 'Когорта',
        desc: 'Cohort study',
        hint: 'Экспозиция → Исход + время',
        targetHint: 'Исход',
        groupHint: 'Экспозиция',
        covHints: ['Возраст', 'Пол', 'Время'],
    },
    {
        id: 'case_control',
        label: 'Случай-контроль',
        desc: 'Case-control',
        hint: 'Факторы риска → Исход',
        targetHint: 'Случай/Контроль',
        groupHint: 'Фактор риска',
        covHints: ['Возраст', 'Пол'],
    },
    {
        id: 'cross_sectional',
        label: 'Поперечное',
        desc: 'Cross-sectional',
        hint: 'Переменная ↔ Переменная',
        targetHint: 'Переменная Y',
        groupHint: 'Переменная X',
        covHints: [],
    },
];

// ── Конфиг цветов ──────────────────────────────────────────────────────────────
const NODE_STYLES = {
    outcome: {
        background: '#d1fae5',
        border: '2px solid #10b981',
        color: '#065f46',
        fontWeight: 700,
    },
    predictor: {
        background: '#dbeafe',
        border: '2px solid #3b82f6',
        color: '#1e40af',
        fontWeight: 700,
    },
    covariate: {
        background: '#f3f4f6',
        border: '1px solid #9ca3af',
        color: '#374151',
        fontWeight: 500,
    },
};

const EDGE_STYLE_MAIN = {
    stroke: '#3b82f6',
    strokeWidth: 2,
};
const EDGE_STYLE_COV = {
    stroke: '#9ca3af',
    strokeWidth: 1.5,
    strokeDasharray: '4 3',
};

// ── roles → nodes + edges ─────────────────────────────────────────────────────
function rolesToFlow(roles) {
    const nodes = [];
    const edges = [];

    if (roles.target) {
        nodes.push({
            id: 'outcome',
            position: { x: 380, y: 120 },
            data: {
                label: roles.target,
                role: 'outcome',
            },
            style: {
                ...NODE_STYLES.outcome,
                borderRadius: 4,
                padding: '8px 16px',
                fontSize: 13,
                minWidth: 120,
                textAlign: 'center',
            },
        });
    }

    if (roles.group) {
        nodes.push({
            id: 'predictor',
            position: { x: 60, y: 120 },
            data: { label: roles.group, role: 'predictor' },
            style: {
                ...NODE_STYLES.predictor,
                borderRadius: 4,
                padding: '8px 16px',
                fontSize: 13,
                minWidth: 120,
                textAlign: 'center',
            },
        });
        if (roles.target) {
            edges.push({
                id: 'e-pred-out',
                source: 'predictor',
                target: 'outcome',
                markerEnd: { type: MarkerType.ArrowClosed, color: '#3b82f6' },
                style: EDGE_STYLE_MAIN,
                label: 'основная гипотеза',
                labelStyle: { fontSize: 10, fill: '#6b7280' },
                labelBgStyle: { fill: 'transparent' },
            });
        }
    }

    const covs = Array.isArray(roles.covariates) ? roles.covariates : [];
    covs.forEach((cov, i) => {
        const id = `cov_${i}`;
        nodes.push({
            id,
            position: { x: 220 + i * 20, y: 260 + i * 10 },
            data: { label: cov, role: 'covariate' },
            style: {
                ...NODE_STYLES.covariate,
                borderRadius: 4,
                padding: '6px 12px',
                fontSize: 12,
                minWidth: 100,
                textAlign: 'center',
            },
        });
        if (roles.target) {
            edges.push({
                id: `e-cov-${i}-out`,
                source: id,
                target: 'outcome',
                markerEnd: { type: MarkerType.ArrowClosed, color: '#9ca3af' },
                style: EDGE_STYLE_COV,
            });
        }
    });

    return { nodes, edges };
}

// ── Легенда ────────────────────────────────────────────────────────────────────
const Legend = () => (
    <div className="flex items-center gap-4 text-[11px] text-[color:var(--text-secondary)]">
        {[
            { color: '#10b981', bg: '#d1fae5', label: 'Исход' },
            { color: '#3b82f6', bg: '#dbeafe', label: 'Предиктор / Группа' },
            { color: '#9ca3af', bg: '#f3f4f6', label: 'Ковариата' },
        ].map(({ color, bg, label }) => (
            <span key={label} className="flex items-center gap-1">
                <span style={{
                    display: 'inline-block',
                    width: 12, height: 12,
                    borderRadius: 2,
                    background: bg,
                    border: `1.5px solid ${color}`,
                }} />
                {label}
            </span>
        ))}
    </div>
);

// ── Пустое состояние ───────────────────────────────────────────────────────────
const EmptyDAG = () => (
    <div className="flex flex-col items-center justify-center h-full text-center gap-3 opacity-60">
        <div className="text-3xl">○ → ○</div>
        <div className="text-sm font-semibold text-[color:var(--text-secondary)]">
            Назначь переменные в рабочей области
        </div>
        <div className="text-xs text-[color:var(--text-muted)]">
            Исход + Группа / Предиктор — и диаграмма появится
        </div>
    </div>
);

// ── Главный компонент ──────────────────────────────────────────────────────────
const StudyDAG = ({ roles, onRolesChange, columns }) => {
    const [activeTemplate, setActiveTemplate] = useState(null);

    const { nodes: initNodes, edges: initEdges } = useMemo(() => rolesToFlow(roles || {}), [roles]);

    const [nodes, setNodes, onNodesChange] = useNodesState(initNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges);

    // Синхронизируем при изменении roles снаружи
    useEffect(() => {
        const { nodes: n, edges: e } = rolesToFlow(roles || {});
        setNodes(n);
        setEdges(e);
    }, [roles, setNodes, setEdges]);

    const onConnect = useCallback(
        (params) => setEdges((eds) => addEdge(params, eds)),
        [setEdges]
    );

    const isEmpty = !roles?.target && !roles?.group;

    return (
        <div className="flex flex-col gap-3">
            {/* Шаблоны */}
            <div>
                <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-2">
                    Шаблон дизайна
                </div>
                <div className="flex flex-wrap gap-1.5">
                    {TEMPLATES.map(tmpl => (
                        <button
                            key={tmpl.id}
                            onClick={() => setActiveTemplate(activeTemplate === tmpl.id ? null : tmpl.id)}
                            title={tmpl.hint}
                            className={`px-2.5 py-1 text-xs font-semibold rounded-[2px] border transition-colors ${activeTemplate === tmpl.id
                                ? 'bg-[color:var(--accent)] text-white border-[color:var(--accent)]'
                                : 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:bg-[color:var(--bg-secondary)]'
                                }`}
                        >
                            {tmpl.label}
                        </button>
                    ))}
                </div>
                {activeTemplate && (() => {
                    const tmpl = TEMPLATES.find(t => t.id === activeTemplate);
                    return (
                        <div className="mt-2 px-3 py-2 rounded-[2px] bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] text-xs text-[color:var(--text-secondary)]">
                            <strong>{tmpl.desc}</strong> — {tmpl.hint}.
                            {' '}Назначь: <em>Исход = {tmpl.targetHint}</em>,{' '}
                            <em>Предиктор = {tmpl.groupHint}</em>
                            {tmpl.covHints.length > 0 && <>, ковариаты: {tmpl.covHints.join(', ')}</>}.
                        </div>
                    );
                })()}
            </div>

            {/* DAG */}
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

            {/* Подсказка */}
            <div className="text-[11px] text-[color:var(--text-muted)]">
                Диаграмма обновляется автоматически при назначении ролей в рабочей области.
                Узлы можно перетаскивать.
            </div>
        </div>
    );
};

export default StudyDAG;
