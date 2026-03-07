import { useCallback, useEffect, useMemo, useState } from 'react';

function parseRepeatedLabel(raw) {
  const s0 = String(raw || '').trim();
  const s = s0.replace(/\s+/g, ' ').trim();
  const m = s.match(/(?:[_\-\s]*[([]?)(\d+)(?:[)\]]?)\s*$/);
  const idx = m ? Number.parseInt(m[1], 10) : null;
  const time = Number.isFinite(idx) ? idx : null;
  const label = s
    .replace(/(?:[_\-\s]*[([]?\d+[)\]]?)\s*$/g, '')
    .replace(/[_\-\s]+$/g, '')
    .trim() || s0;
  const key = String(label).toLowerCase() || s0.toLowerCase();
  return { key, label, time };
}

export default function useRepeatedOutcomeGroups({
  columns,
  methodId,
  isRepeatedMeasures,
  setVariables,
}) {
  const [rmBaseKey, setRmBaseKey] = useState('');

  const repeatedOutcomeGroups = useMemo(() => {
    const list = Array.isArray(columns) ? columns : [];
    const names = list
      .map((c) => (typeof c === 'string' ? c : c?.name))
      .filter(Boolean)
      .map((n) => String(n));

    const minPoints = methodId === 'friedman' ? 3 : 2;
    const byBase = new Map();

    for (const n of names) {
      const p = parseRepeatedLabel(n);
      const k = p.key;
      if (!byBase.has(k)) byBase.set(k, { cols: [], labels: new Map() });
      const entry = byBase.get(k);
      entry.cols.push(n);
      const lab = String(p.label || '').trim();
      if (lab) entry.labels.set(lab, (entry.labels.get(lab) || 0) + 1);
    }

    return Array.from(byBase.entries())
      .map(([k, entry]) => {
        const cols = Array.isArray(entry?.cols) ? entry.cols : [];
        const labels = entry?.labels instanceof Map ? entry.labels : new Map();
        const label = Array.from(labels.entries())
          .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length || a[0].localeCompare(b[0], 'ru'))
          .map(([name]) => name)[0] || k;

        const sorted = [...cols].sort((a, b) => {
          const ia = parseRepeatedLabel(a).time;
          const ib = parseRepeatedLabel(b).time;
          if (ia == null && ib == null) return a.localeCompare(b, 'ru');
          if (ia == null) return 1;
          if (ib == null) return -1;
          return ia - ib;
        });
        const indices = sorted
          .map((c) => parseRepeatedLabel(c).time)
          .filter((x) => x != null);
        const uniqIndices = Array.from(new Set(indices)).sort((a, b) => a - b);

        return { key: k, label, cols: sorted, indices: uniqIndices };
      })
      .filter((g) => g.cols.length >= minPoints)
      .sort((a, b) => b.cols.length - a.cols.length || String(a.label).localeCompare(String(b.label), 'ru'));
  }, [columns, methodId]);

  const rmTimeIndex = useCallback((raw) => {
    const s = String(raw || '').trim();
    const m = s.match(/(?:[_\-\s]*[([]?)(\d+)(?:[)\]]?)\s*$/);
    if (!m) return null;
    const n = Number.parseInt(m[1], 10);
    return Number.isFinite(n) ? n : null;
  }, []);

  const rmGroup = useMemo(() => {
    const keys = repeatedOutcomeGroups.map((g) => g.key);
    const resolvedBase =
      isRepeatedMeasures && (!rmBaseKey || !keys.includes(rmBaseKey))
        ? (keys[0] || '')
        : rmBaseKey;
    if (!resolvedBase) return null;
    return repeatedOutcomeGroups.find((g) => g.key === resolvedBase) || null;
  }, [isRepeatedMeasures, repeatedOutcomeGroups, rmBaseKey]);

  const effectiveRmBaseKey = useMemo(() => {
    const keys = repeatedOutcomeGroups.map((g) => g.key);
    if (!isRepeatedMeasures) return rmBaseKey;
    if (rmBaseKey && keys.includes(rmBaseKey)) return rmBaseKey;
    return keys[0] || '';
  }, [isRepeatedMeasures, repeatedOutcomeGroups, rmBaseKey]);

  useEffect(() => {
    if (!isRepeatedMeasures) return;
    if (!rmGroup) return;
    setVariables((v) => {
      const current = Array.isArray(v.outcome_cols) ? v.outcome_cols : [];
      const groupSet = new Set(rmGroup.cols.map(String));
      const hasForeign = current.some((c) => !groupSet.has(String(c)));
      if (current.length === 0 || hasForeign) {
        return { ...v, outcome_cols: rmGroup.cols };
      }
      const next = current.filter((c) => groupSet.has(String(c)));
      return next.length ? { ...v, outcome_cols: next } : { ...v, outcome_cols: rmGroup.cols };
    });
  }, [isRepeatedMeasures, rmGroup, setVariables]);

  return {
    rmBaseKey: effectiveRmBaseKey,
    setRmBaseKey,
    repeatedOutcomeGroups,
    rmGroup,
    rmTimeIndex,
  };
}
