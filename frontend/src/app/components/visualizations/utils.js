
export const formatP = (v) => {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—';
  if (v < 0.001) return '< 0.001';
  return v.toFixed(4);
};

export const formatNum = (v, digits = 2) => {
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n)) return '—';
  return n.toFixed(digits);
};

export const formatGroupCell = (s) => {
    if (!s) return '—';
    const mean = s.mean;
    const sd = s.sd;
    if (typeof mean !== 'number' || typeof sd !== 'number') return '—';
    return `${mean.toFixed(2)} ± ${sd.toFixed(2)}`;
};

export const pClass = (p) => {
    if (typeof p !== 'number') return 'text-[color:var(--text-secondary)]';
    if (p < 0.05) return 'text-[color:var(--success)]';
    return 'text-[color:var(--text-secondary)]';
};

export const getPostHocRows = (postHoc) => {
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

export const getGroupStatsRows = (plotStats) => {
  if (!plotStats || typeof plotStats !== 'object') return [];
  return Object.entries(plotStats)
    .sort(([a], [b]) => String(a).localeCompare(String(b)))
    .map(([groupName, s]) => ({ groupName, s }));
};

export const getEffectColor = (val) => {
    if (typeof val !== 'number') return 'text-[color:var(--text-muted)]';
    const v = Math.abs(val);
    if (v < 0.2) return 'text-yellow-600'; 
    if (v < 0.5) return 'text-orange-500';
    return 'text-[color:var(--success)]';
};
