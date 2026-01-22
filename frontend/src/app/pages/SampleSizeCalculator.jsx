import React, { useMemo, useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs';
import Input from '../components/ui/Input';
import { getAlphaSetting } from '../../lib/api';
import { StatTooltip } from '../components/education';

function clamp01(x) {
  if (!Number.isFinite(x)) return null;
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}

function normInv(p) {
  const pp = Number(p);
  if (!Number.isFinite(pp)) return null;
  if (pp <= 0 || pp >= 1) return null;

  const a = [
    -3.969683028665376e+01,
    2.209460984245205e+02,
    -2.759285104469687e+02,
    1.383577518672690e+02,
    -3.066479806614716e+01,
    2.506628277459239e+00,
  ];
  const b = [
    -5.447609879822406e+01,
    1.615858368580409e+02,
    -1.556989798598866e+02,
    6.680131188771972e+01,
    -1.328068155288572e+01,
  ];
  const c = [
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e+00,
    -2.549732539343734e+00,
    4.374664141464968e+00,
    2.938163982698783e+00,
  ];
  const d = [
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e+00,
    3.754408661907416e+00,
  ];

  const plow = 0.02425;
  const phigh = 1 - plow;

  if (pp < plow) {
    const q = Math.sqrt(-2 * Math.log(pp));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }

  if (pp > phigh) {
    const q = Math.sqrt(-2 * Math.log(1 - pp));
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }

  const q = pp - 0.5;
  const r = q * q;
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}

function zForAlpha(alpha, sided) {
  const a = clamp01(alpha);
  if (!a || a <= 0 || a >= 1) return null;
  const tail = sided === 'one' ? a : a / 2;
  return normInv(1 - tail);
}

function zForPower(power) {
  const p = clamp01(power);
  if (!p || p <= 0 || p >= 1) return null;
  return normInv(p);
}

function formatInt(x) {
  if (!Number.isFinite(x)) return '—';
  return String(Math.ceil(x));
}

function formatFloat(x, digits = 3) {
  if (!Number.isFinite(x)) return '—';
  return Number(x).toFixed(digits);
}

function parseNum(v) {
  const s = String(v ?? '').trim();
  if (!s) return null;
  const n = Number(s.replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

function clampMin(x, min) {
  if (!Number.isFinite(x)) return null;
  if (x < min) return min;
  return x;
}

function ceilInt(x) {
  if (!Number.isFinite(x)) return null;
  if (x <= 0) return null;
  return Math.ceil(x);
}

function ratioLabel(k) {
  if (!Number.isFinite(k) || k <= 0) return '—';
  if (Math.abs(k - 1) < 1e-9) return '1:1';
  if (k > 1) return `1:${formatFloat(k, 2)}`;
  return `${formatFloat(1 / k, 2)}:1`;
}

export default function SampleSizeCalculator() {
  const [tab, setTab] = useState('means');

  const [sided, setSided] = useState('two');
  const [alpha, setAlpha] = useState(() => {
    const a = Number(getAlphaSetting());
    return Number.isFinite(a) ? a : 0.05;
  });
  const [power, setPower] = useState(0.8);

  const [correction, setCorrection] = useState('none');
  const [comparisons, setComparisons] = useState('1');
  const [allocationRatio, setAllocationRatio] = useState('1');
  const [attrition, setAttrition] = useState('0');

  const [meansMode, setMeansMode] = useState('d');
  const [d, setD] = useState('0.5');
  const [mean1, setMean1] = useState('100');
  const [mean2, setMean2] = useState('110');
  const [sd, setSd] = useState('20');

  const [p1, setP1] = useState('0.30');
  const [p2, setP2] = useState('0.40');

  const [r, setR] = useState('0.30');

  const comparisonsN = useMemo(() => {
    const raw = parseNum(comparisons);
    const n = raw === null ? null : Math.floor(raw);
    if (n === null) return 1;
    return Math.max(1, n);
  }, [comparisons]);

  const alphaEffective = useMemo(() => {
    const a = clamp01(alpha);
    if (!a) return null;
    if (correction === 'bonferroni') {
      return clamp01(a / comparisonsN);
    }
    return a;
  }, [alpha, correction, comparisonsN]);

  const dropoutRate = useMemo(() => {
    const v = parseNum(attrition);
    if (v === null) return 0;
    return Math.max(0, Math.min(0.95, v));
  }, [attrition]);

  const kRatio = useMemo(() => {
    const k = parseNum(allocationRatio);
    return clampMin(k, 0.05);
  }, [allocationRatio]);

  const zAlpha = useMemo(() => zForAlpha(alphaEffective, sided), [alphaEffective, sided]);
  const zBeta = useMemo(() => zForPower(power), [power]);

  const derivedEffect = useMemo(() => {
    if (tab !== 'means') return null;
    if (meansMode === 'd') return Math.abs(parseNum(d) ?? NaN);
    const m1 = parseNum(mean1);
    const m2 = parseNum(mean2);
    const s = parseNum(sd);
    if (!m1 && m1 !== 0) return null;
    if (!m2 && m2 !== 0) return null;
    if (!s || s <= 0) return null;
    const delta = Math.abs(m2 - m1);
    return delta / s;
  }, [tab, meansMode, d, mean1, mean2, sd]);

  const meansResult = useMemo(() => {
    if (tab !== 'means') return null;
    const effect = derivedEffect;
    if (!Number.isFinite(effect) || effect <= 0) return { ok: false, message: 'Задайте эффект больше 0.' };
    if (!Number.isFinite(zAlpha) || !Number.isFinite(zBeta)) return { ok: false, message: 'Проверьте α и мощность.' };
    if (!Number.isFinite(kRatio) || kRatio <= 0) return { ok: false, message: 'Проверьте соотношение групп.' };

    const n1 = Math.pow((zAlpha + zBeta) / effect, 2) * (1 + 1 / kRatio);
    const n2 = n1 * kRatio;

    const n1Ceil = ceilInt(n1);
    const n2Ceil = ceilInt(n2);
    if (!n1Ceil || !n2Ceil) return { ok: false, message: 'Не удалось посчитать n.' };

    const analyzedTotal = n1Ceil + n2Ceil;
    const inflate = dropoutRate > 0 ? 1 / (1 - dropoutRate) : 1;
    const recruitN1 = ceilInt(n1Ceil * inflate);
    const recruitN2 = ceilInt(n2Ceil * inflate);

    return {
      ok: true,
      n1: n1Ceil,
      n2: n2Ceil,
      analyzedTotal,
      recruitN1,
      recruitN2,
      recruitTotal: recruitN1 && recruitN2 ? recruitN1 + recruitN2 : null,
      effect,
      k: kRatio,
    };
  }, [tab, derivedEffect, dropoutRate, kRatio, zAlpha, zBeta]);

  const propsResult = useMemo(() => {
    if (tab !== 'props') return null;
    const a = clamp01(alphaEffective);
    const pw = clamp01(power);
    const x1 = clamp01(parseNum(p1));
    const x2 = clamp01(parseNum(p2));
    if (!a || !pw) return { ok: false, message: 'Проверьте α и мощность.' };
    if (x1 === null || x2 === null) return { ok: false, message: 'Введите доли в диапазоне 0…1.' };
    if (x1 <= 0 || x1 >= 1 || x2 <= 0 || x2 >= 1) return { ok: false, message: 'Доли должны быть строго между 0 и 1.' };
    if (!Number.isFinite(zAlpha) || !Number.isFinite(zBeta)) return { ok: false, message: 'Проверьте α и мощность.' };
    if (!Number.isFinite(kRatio) || kRatio <= 0) return { ok: false, message: 'Проверьте соотношение групп.' };
    const delta = Math.abs(x2 - x1);
    if (delta <= 0) return { ok: false, message: 'Разница долей должна быть больше 0.' };

    const pBar = (x1 + x2) / 2;
    const term1 = zAlpha * Math.sqrt(pBar * (1 - pBar) * (1 + 1 / kRatio));
    const term2 = zBeta * Math.sqrt(x1 * (1 - x1) + (x2 * (1 - x2)) / kRatio);
    const n1 = Math.pow(term1 + term2, 2) / Math.pow(delta, 2);
    const n2 = n1 * kRatio;

    const n1Ceil = ceilInt(n1);
    const n2Ceil = ceilInt(n2);
    if (!n1Ceil || !n2Ceil) return { ok: false, message: 'Не удалось посчитать n.' };

    const analyzedTotal = n1Ceil + n2Ceil;
    const inflate = dropoutRate > 0 ? 1 / (1 - dropoutRate) : 1;
    const recruitN1 = ceilInt(n1Ceil * inflate);
    const recruitN2 = ceilInt(n2Ceil * inflate);

    return {
      ok: true,
      n1: n1Ceil,
      n2: n2Ceil,
      analyzedTotal,
      recruitN1,
      recruitN2,
      recruitTotal: recruitN1 && recruitN2 ? recruitN1 + recruitN2 : null,
      delta,
      k: kRatio,
      p1: x1,
      p2: x2,
    };
  }, [tab, alphaEffective, dropoutRate, kRatio, p1, p2, power, zAlpha, zBeta]);

  const corrResult = useMemo(() => {
    if (tab !== 'corr') return null;
    const a = clamp01(alphaEffective);
    const pw = clamp01(power);
    const rr = parseNum(r);
    if (!a || !pw) return { ok: false, message: 'Проверьте α и мощность.' };
    if (!Number.isFinite(rr)) return { ok: false, message: 'Введите r.' };
    const absR = Math.abs(rr);
    if (absR <= 0 || absR >= 1) return { ok: false, message: 'r должен быть между 0 и 1.' };
    if (!Number.isFinite(zAlpha) || !Number.isFinite(zBeta)) return { ok: false, message: 'Проверьте α и мощность.' };
    const fisher = 0.5 * Math.log((1 + absR) / (1 - absR));
    const n = Math.pow((zAlpha + zBeta) / fisher, 2) + 3;
    if (!Number.isFinite(n) || n <= 0) return { ok: false, message: 'Не удалось посчитать n.' };
    const analyzedTotal = Math.ceil(n);
    const inflate = dropoutRate > 0 ? 1 / (1 - dropoutRate) : 1;
    const recruitTotal = ceilInt(analyzedTotal * inflate);
    return {
      ok: true,
      analyzedTotal,
      recruitTotal,
      absR,
    };
  }, [tab, alphaEffective, dropoutRate, power, r, zAlpha, zBeta]);

  const activeResult = tab === 'means' ? meansResult : tab === 'props' ? propsResult : corrResult;

  const sensitivity = useMemo(() => {
    if (!activeResult?.ok) return [];
    const z = zAlpha + zBeta;
    if (!Number.isFinite(z) || z <= 0) return [];

    if (tab === 'means') {
      const effect = meansResult?.effect;
      if (!Number.isFinite(effect) || effect <= 0) return [];
      const k = meansResult?.k;
      if (!Number.isFinite(k) || k <= 0) return [];
      const multipliers = [0.8, 1, 1.25];
      return multipliers.map((m) => {
        const dEff = effect * m;
        const n1 = Math.pow(z / dEff, 2) * (1 + 1 / k);
        const n2 = n1 * k;
        const n1Ceil = ceilInt(n1);
        const n2Ceil = ceilInt(n2);
        return { key: `d_${m}`, label: `d×${m}`, total: (n1Ceil && n2Ceil) ? n1Ceil + n2Ceil : null };
      }).filter((x) => x.total);
    }

    if (tab === 'props') {
      const delta = propsResult?.delta;
      const k = propsResult?.k;
      const x1 = propsResult?.p1;
      const x2 = propsResult?.p2;
      if (!Number.isFinite(delta) || delta <= 0) return [];
      if (!Number.isFinite(k) || k <= 0) return [];
      if (!Number.isFinite(x1) || !Number.isFinite(x2)) return [];

      const pBar = (x1 + x2) / 2;
      const multipliers = [0.8, 1, 1.25];
      return multipliers.map((m) => {
        const dEff = delta * m;
        const term1 = zAlpha * Math.sqrt(pBar * (1 - pBar) * (1 + 1 / k));
        const term2 = zBeta * Math.sqrt(x1 * (1 - x1) + (x2 * (1 - x2)) / k);
        const n1 = Math.pow(term1 + term2, 2) / Math.pow(dEff, 2);
        const n2 = n1 * k;
        const n1Ceil = ceilInt(n1);
        const n2Ceil = ceilInt(n2);
        return { key: `dp_${m}`, label: `Δp×${m}`, total: (n1Ceil && n2Ceil) ? n1Ceil + n2Ceil : null };
      }).filter((x) => x.total);
    }

    const absR = corrResult?.absR;
    if (!Number.isFinite(absR) || absR <= 0 || absR >= 1) return [];
    const multipliers = [0.8, 1, 1.25];
    return multipliers.map((m) => {
      const rr = Math.min(0.999, absR * m);
      const fisher = 0.5 * Math.log((1 + rr) / (1 - rr));
      const n = Math.pow(z / fisher, 2) + 3;
      return { key: `r_${m}`, label: `r×${m}`, total: ceilInt(n) };
    }).filter((x) => x.total);
  }, [activeResult?.ok, corrResult?.absR, meansResult?.effect, meansResult?.k, propsResult?.delta, propsResult?.k, propsResult?.p1, propsResult?.p2, tab, zAlpha, zBeta]);

  return (
    <div className="max-w-[1200px]">
      <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-8 items-start">
        <div className="sticky top-20">
          <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Калькулятор</div>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-[color:var(--text-primary)]">Размер выборки</h1>
          <div className="mt-2 text-sm text-[color:var(--text-secondary)] leading-relaxed">
            Быстрые оценки для планирования. Формулы — нормальная аппроксимация; для точного расчёта учитывайте дизайн и данные.
          </div>

          <div className="mt-6 grid grid-cols-2 gap-4">
            <label className="grid gap-1">
              <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">
                <StatTooltip term="alpha" level="junior" position="right"><span>α err prob</span></StatTooltip>
              </div>
              <Input
                inputMode="decimal"
                value={String(alpha)}
                onChange={(e) => {
                  const v = parseNum(e.target.value);
                  if (v === null) setAlpha(e.target.value);
                  else setAlpha(v);
                }}
                placeholder="0.05"
                aria-label="Alpha"
              />
            </label>
            <label className="grid gap-1">
              <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">
                <StatTooltip term="power" level="junior" position="right"><span>Power (1−β)</span></StatTooltip>
              </div>
              <Input
                inputMode="decimal"
                value={String(power)}
                onChange={(e) => {
                  const v = parseNum(e.target.value);
                  if (v === null) setPower(e.target.value);
                  else setPower(v);
                }}
                placeholder="0.80"
                aria-label="Power"
              />
            </label>

            <label className="grid gap-1 col-span-2">
              <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Хвосты</div>
              <select
                value={sided}
                onChange={(e) => setSided(e.target.value)}
                className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
              >
                <option value="two">Двусторонний тест</option>
                <option value="one">Односторонний тест</option>
              </select>
            </label>

            <label className="grid gap-1 col-span-2">
              <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">
                <StatTooltip term="multiple_comparison" level="junior" position="right"><span>Поправка за множественность</span></StatTooltip>
              </div>
              <div className="grid grid-cols-[1fr_140px] gap-3">
                <select
                  value={correction}
                  onChange={(e) => setCorrection(e.target.value)}
                  className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                >
                  <option value="none">Без поправки (одна первичная гипотеза)</option>
                  <option value="bonferroni">Bonferroni: α / m</option>
                </select>
                <Input
                  inputMode="numeric"
                  value={String(comparisons)}
                  onChange={(e) => setComparisons(e.target.value)}
                  placeholder="m"
                  aria-label="Количество сравнений"
                  disabled={correction !== 'bonferroni'}
                />
              </div>
              <div className="text-[11px] text-[color:var(--text-muted)]">
                α для расчёта: <span className="font-mono text-[color:var(--text-primary)]">{formatFloat(alphaEffective, 5)}</span>
              </div>
            </label>

            <label className="grid gap-1">
              <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Allocation ratio</div>
              <Input
                inputMode="decimal"
                value={String(allocationRatio)}
                onChange={(e) => setAllocationRatio(e.target.value)}
                placeholder="1"
                aria-label="Соотношение групп (N2/N1)"
              />
              <div className="text-[11px] text-[color:var(--text-muted)]">N1:N2 = <span className="font-mono">{ratioLabel(kRatio)}</span></div>
            </label>

            <label className="grid gap-1">
              <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Dropout</div>
              <Input
                inputMode="decimal"
                value={String(attrition)}
                onChange={(e) => setAttrition(e.target.value)}
                placeholder="0"
                aria-label="Ожидаемая доля выбывших"
              />
              <div className="text-[11px] text-[color:var(--text-muted)]">в долях: 0…0.95 (например 0.15)</div>
            </label>
          </div>

          <div className="mt-8">
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList>
                <TabsTrigger value="means">Средние</TabsTrigger>
                <TabsTrigger value="props">Доли</TabsTrigger>
                <TabsTrigger value="corr">Корреляция</TabsTrigger>
              </TabsList>

              <TabsContent value="means" className="pt-6">
                <div className="grid grid-cols-1 gap-4">
                  <label className="grid gap-1">
                    <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Как задать эффект</div>
                    <select
                      value={meansMode}
                      onChange={(e) => setMeansMode(e.target.value)}
                      className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                    >
                      <option value="d">Cohen’s d (готовый)</option>
                      <option value="means">Δ и SD</option>
                    </select>
                  </label>

                  {meansMode === 'd' ? (
                    <label className="grid gap-1">
                      <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">
                        <StatTooltip term="cohens_d" level="junior" position="right"><span>Effect size d</span></StatTooltip>
                      </div>
                      <Input inputMode="decimal" value={d} onChange={(e) => setD(e.target.value)} placeholder="0.5" />
                      <div className="flex flex-wrap gap-2 pt-1">
                        {[
                          { label: 'малый', v: 0.2 },
                          { label: 'средний', v: 0.5 },
                          { label: 'большой', v: 0.8 },
                        ].map((x) => (
                          <button
                            key={x.label}
                            type="button"
                            onClick={() => setD(String(x.v))}
                            className="h-8 px-3 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-black tracking-widest text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)] transition-colors"
                          >
                            {x.label} · d={formatFloat(x.v, 1)}
                          </button>
                        ))}
                      </div>
                      <div className="text-[11px] text-[color:var(--text-muted)] leading-relaxed">
                        Если «d неизвестен»: сначала выберите клинически важную разницу Δ, оцените SD по пилоту/литературе и переключитесь на «Δ и SD».
                      </div>
                    </label>
                  ) : (
                    <div className="grid grid-cols-3 gap-4">
                      <label className="grid gap-1">
                        <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Среднее A</div>
                        <Input inputMode="decimal" value={mean1} onChange={(e) => setMean1(e.target.value)} />
                      </label>
                      <label className="grid gap-1">
                        <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Среднее B</div>
                        <Input inputMode="decimal" value={mean2} onChange={(e) => setMean2(e.target.value)} />
                      </label>
                      <label className="grid gap-1">
                        <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">SD (общая)</div>
                        <Input inputMode="decimal" value={sd} onChange={(e) => setSd(e.target.value)} />
                      </label>
                    </div>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="props" className="pt-6">
                <div className="grid grid-cols-2 gap-4">
                  <label className="grid gap-1">
                    <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Доля A</div>
                    <Input inputMode="decimal" value={p1} onChange={(e) => setP1(e.target.value)} placeholder="0.30" />
                  </label>
                  <label className="grid gap-1">
                    <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Доля B</div>
                    <Input inputMode="decimal" value={p2} onChange={(e) => setP2(e.target.value)} placeholder="0.40" />
                  </label>
                  <div className="col-span-2 text-[11px] text-[color:var(--text-muted)] leading-relaxed">
                    Вводите ожидаемые доли в каждой группе (0…1). Если хотите «минимально важную разницу», держите одну долю фиксированной (baseline) и двигайте вторую.
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="corr" className="pt-6">
                <div className="grid grid-cols-1 gap-4">
                  <label className="grid gap-1">
                    <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Ожидаемая |r|</div>
                    <Input inputMode="decimal" value={r} onChange={(e) => setR(e.target.value)} placeholder="0.30" />
                    <div className="flex flex-wrap gap-2 pt-1">
                      {[
                        { label: 'слабая', v: 0.1 },
                        { label: 'умеренная', v: 0.3 },
                        { label: 'сильная', v: 0.5 },
                      ].map((x) => (
                        <button
                          key={x.label}
                          type="button"
                          onClick={() => setR(String(x.v))}
                          className="h-8 px-3 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-black tracking-widest text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)] transition-colors"
                        >
                          {x.label} · r={formatFloat(x.v, 1)}
                        </button>
                      ))}
                    </div>
                  </label>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>

        <div>
          <div className="card overflow-hidden">
            <div className="px-6 py-5 border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
              <div className="flex items-baseline justify-between gap-6">
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Результат</div>
                  <div className="mt-2 text-xl font-black tracking-tight text-[color:var(--text-primary)]">Оценка нужного n</div>
                </div>
                <div className="text-right">
                  <div className="text-[11px] font-semibold text-[color:var(--text-secondary)]">z(α)</div>
                  <div className="font-mono text-sm text-[color:var(--text-primary)]">{formatFloat(zAlpha, 3)}</div>
                </div>
              </div>
            </div>

            <div className="px-6 py-6 bg-[color:var(--white)]">
              {activeResult?.ok ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="border border-[color:var(--border-color)] rounded-[2px] p-5">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Сколько нужно</div>
                    {tab === 'corr' ? (
                      <div className="mt-3">
                        <div className="text-4xl font-black tracking-tight text-[color:var(--text-primary)]">{formatInt(activeResult.analyzedTotal)}</div>
                        <div className="mt-1 text-xs text-[color:var(--text-secondary)]">анализируемых объектов</div>
                        {dropoutRate > 0 && activeResult.recruitTotal ? (
                          <div className="mt-3">
                            <div className="text-[11px] font-semibold text-[color:var(--text-secondary)]">с учётом dropout</div>
                            <div className="font-mono text-sm text-[color:var(--text-primary)]">набрать: {formatInt(activeResult.recruitTotal)}</div>
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div className="mt-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <div className="text-4xl font-black tracking-tight text-[color:var(--text-primary)]">{formatInt(activeResult.n1)}</div>
                            <div className="mt-1 text-xs text-[color:var(--text-secondary)]">группа 1</div>
                          </div>
                          <div>
                            <div className="text-4xl font-black tracking-tight text-[color:var(--text-primary)]">{formatInt(activeResult.n2)}</div>
                            <div className="mt-1 text-xs text-[color:var(--text-secondary)]">группа 2</div>
                          </div>
                        </div>
                        <div className="mt-3 font-mono text-xs text-[color:var(--text-muted)]">итого (анализ): {formatInt(activeResult.analyzedTotal)}</div>
                        {dropoutRate > 0 && activeResult.recruitN1 && activeResult.recruitN2 ? (
                          <div className="mt-2 font-mono text-xs text-[color:var(--text-muted)]">набрать: {formatInt(activeResult.recruitN1)} + {formatInt(activeResult.recruitN2)} = {formatInt(activeResult.recruitTotal)}</div>
                        ) : null}
                      </div>
                    )}
                  </div>

                  <div className="border border-[color:var(--border-color)] rounded-[2px] p-5">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Что заложено</div>
                    <div className="mt-3 space-y-2 text-sm">
                      <div className="flex items-baseline justify-between gap-3">
                        <div className="text-[color:var(--text-secondary)]">α</div>
                        <div className="font-mono text-[color:var(--text-primary)]">{formatFloat(alphaEffective, 5)}</div>
                      </div>
                      <div className="flex items-baseline justify-between gap-3">
                        <div className="text-[color:var(--text-secondary)]">power</div>
                        <div className="font-mono text-[color:var(--text-primary)]">{formatFloat(power, 3)}</div>
                      </div>
                      <div className="flex items-baseline justify-between gap-3">
                        <div className="text-[color:var(--text-secondary)]">тест</div>
                        <div className="font-mono text-[color:var(--text-primary)]">{sided === 'two' ? 'two-sided' : 'one-sided'}</div>
                      </div>
                      {tab !== 'corr' ? (
                        <div className="flex items-baseline justify-between gap-3">
                          <div className="text-[color:var(--text-secondary)]">N2/N1</div>
                          <div className="font-mono text-[color:var(--text-primary)]">{formatFloat(kRatio, 3)}</div>
                        </div>
                      ) : null}
                      {correction === 'bonferroni' ? (
                        <div className="flex items-baseline justify-between gap-3">
                          <div className="text-[color:var(--text-secondary)]">m</div>
                          <div className="font-mono text-[color:var(--text-primary)]">{formatInt(comparisonsN)}</div>
                        </div>
                      ) : null}
                      {dropoutRate > 0 ? (
                        <div className="flex items-baseline justify-between gap-3">
                          <div className="text-[color:var(--text-secondary)]">dropout</div>
                          <div className="font-mono text-[color:var(--text-primary)]">{formatFloat(dropoutRate, 2)}</div>
                        </div>
                      ) : null}
                      {tab === 'means' ? (
                        <div className="flex items-baseline justify-between gap-3">
                          <div className="text-[color:var(--text-secondary)]">d</div>
                          <div className="font-mono text-[color:var(--text-primary)]">{formatFloat(meansResult.effect, 3)}</div>
                        </div>
                      ) : null}
                      {tab === 'props' ? (
                        <div className="flex items-baseline justify-between gap-3">
                          <div className="text-[color:var(--text-secondary)]">Δp</div>
                          <div className="font-mono text-[color:var(--text-primary)]">{formatFloat(propsResult.delta, 3)}</div>
                        </div>
                      ) : null}
                      {tab === 'corr' ? (
                        <div className="flex items-baseline justify-between gap-3">
                          <div className="text-[color:var(--text-secondary)]">|r|</div>
                          <div className="font-mono text-[color:var(--text-primary)]">{formatFloat(corrResult.absR, 3)}</div>
                        </div>
                      ) : null}
                      <div className="flex items-baseline justify-between gap-3">
                        <div className="text-[color:var(--text-secondary)]">z(β)</div>
                        <div className="font-mono text-[color:var(--text-primary)]">{formatFloat(zBeta, 3)}</div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-6 bg-[color:var(--bg-tertiary)]">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Нужно чуть больше данных</div>
                  <div className="mt-2 text-sm text-[color:var(--text-secondary)]">{activeResult?.message || 'Заполните поля слева.'}</div>
                </div>
              )}

              {activeResult?.ok && sensitivity.length ? (
                <div className="mt-8 border border-[color:var(--border-color)] rounded-[2px] p-5">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Если эффект окажется другим</div>
                  <div className="mt-2 text-xs text-[color:var(--text-muted)]">n растёт примерно как 1/(effect²). Ниже — быстрый «коридор».</div>
                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {sensitivity.map((row) => (
                      <div key={row.key} className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-tertiary)]">
                        <div className="text-[11px] font-black tracking-widest uppercase text-[color:var(--text-secondary)]">{row.label}</div>
                        <div className="mt-2 text-2xl font-black text-[color:var(--text-primary)]">{formatInt(row.total)}</div>
                        <div className="text-[11px] text-[color:var(--text-muted)]">итого (анализ)</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="mt-8 text-xs text-[color:var(--text-muted)] leading-relaxed">
                Это оценки как в G*Power: effect size + α err prob + power + tails (+ allocation ratio). Если дизайн сложнее (кластеризация/повторы/ковариаты) — эти n скорее нижняя граница.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
