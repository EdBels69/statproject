import React, { useMemo, useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs';
import { useLanguage } from '../../contexts/LanguageContext';
import { getKnowledgeManual, getKnowledgeTerm, getKnowledgeTerms, getKnowledgeTest, getKnowledgeTests } from '../../lib/api';

function createResource(load) {
  let status = 'pending';
  let value;

  const suspender = Promise.resolve()
    .then(load)
    .then(
      (data) => {
        status = 'success';
        value = data;
      },
      (err) => {
        status = 'error';
        value = err;
      },
    );

  return {
    read() {
      if (status === 'pending') throw suspender;
      if (status === 'error') throw value;
      return value;
    },
  };
}

function normalizeList(items) {
  return (Array.isArray(items) ? items : [])
    .filter(Boolean)
    .map((x) => ({
      key: String(x.key || ''),
      term: String(x.term || ''),
      term_ru: String(x.term_ru || ''),
      name: String(x.name || ''),
      name_ru: String(x.name_ru || ''),
      emoji: String(x.emoji || '📊'),
    }))
    .filter((x) => x.key);
}

function splitParagraphs(text) {
  const s = String(text || '').trim();
  if (!s) return [];
  return s.split(/\n\s*\n/g).map((p) => p.trim()).filter(Boolean);
}

function normalizeAlternatives(alt) {
  if (!alt || typeof alt !== 'object') return [];
  return Object.entries(alt)
    .map(([key, value]) => {
      if (!value || typeof value !== 'object') {
        return { key: String(key), title: String(key), body: [{ k: '', v: String(value ?? '') }] };
      }
      const test = value.test ? String(value.test) : '';
      const reason = value.reason ? String(value.reason) : '';
      const title = reason ? String(reason) : (test ? test : String(key));
      const body = [
        ...(test ? [{ k: 'test', v: test }] : []),
        ...(reason ? [{ k: 'why', v: reason }] : []),
      ];
      return { key: String(key), title, body };
    })
    .filter((x) => x.key);
}

function formatDoi(doi) {
  const s = String(doi || '').trim();
  if (!s) return null;
  if (s.startsWith('http://') || s.startsWith('https://')) return s;
  return `https://doi.org/${s}`;
}

function pickTitle(entry, kind) {
  if (!entry) return '';
  if (kind === 'tests') return entry.name_ru || entry.name || entry.key;
  return entry.term_ru || entry.term || entry.key;
}

export default function StatWiki() {
  const { educationLevel } = useLanguage();

  const [tab, setTab] = useState('terms');
  const level = educationLevel || 'junior';

  const listResource = useMemo(() => {
    return createResource(async () => {
      const [termsRes, testsRes] = await Promise.all([getKnowledgeTerms(), getKnowledgeTests()]);
      const termList = normalizeList(termsRes?.terms);
      const testList = normalizeList(testsRes?.tests);
      termList.sort((a, b) => pickTitle(a, 'terms').localeCompare(pickTitle(b, 'terms'), 'ru'));
      testList.sort((a, b) => pickTitle(a, 'tests').localeCompare(pickTitle(b, 'tests'), 'ru'));
      return { termList, testList };
    });
  }, []);

  return (
    <React.Suspense
      fallback={(
        <div className="max-w-[1400px]">
          <div className="text-sm text-[color:var(--text-secondary)]">Загрузка справочника…</div>
        </div>
      )}
    >
      <StatWikiContent
        tab={tab}
        setTab={setTab}
        level={level}
        listResource={listResource}
      />
    </React.Suspense>
  );
}

function renderMarkdownBlocks(markdown) {
  const lines = String(markdown || '').replace(/\r\n/g, '\n').split('\n');
  const blocks = [];
  let i = 0;
  let key = 0;

  const takeParagraph = () => {
    const parts = [];
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) break;
      if (/^#{1,6}\s+/.test(line)) break;
      if (/^```/.test(line)) break;
      if (/^\s*[-*+]\s+/.test(line)) break;
      if (/^\s*\d+\.\s+/.test(line)) break;
      parts.push(line.trim());
      i += 1;
    }
    const text = parts.join(' ');
    if (text) blocks.push({ type: 'p', key: key++, text });
  };

  const takeList = (ordered) => {
    const items = [];
    while (i < lines.length) {
      const line = lines[i];
      const m = ordered ? line.match(/^\s*(\d+)\.\s+(.+)$/) : line.match(/^\s*[-*+]\s+(.+)$/);
      if (!m) break;
      items.push((ordered ? m[2] : m[1]).trim());
      i += 1;
    }
    if (items.length) blocks.push({ type: ordered ? 'ol' : 'ul', key: key++, items });
  };

  const takeCode = () => {
    const fence = lines[i];
    const lang = fence.replace(/^```\s*/, '').trim();
    i += 1;
    const body = [];
    while (i < lines.length && !/^```\s*$/.test(lines[i])) {
      body.push(lines[i]);
      i += 1;
    }
    if (i < lines.length && /^```\s*$/.test(lines[i])) i += 1;
    blocks.push({ type: 'code', key: key++, lang, text: body.join('\n') });
  };

  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.trimEnd();
    if (!line.trim()) {
      i += 1;
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const depth = heading[1].length;
      blocks.push({ type: 'h', key: key++, depth, text: heading[2].trim() });
      i += 1;
      continue;
    }
    if (/^```/.test(line)) {
      takeCode();
      continue;
    }
    if (/^\s*[-*+]\s+/.test(raw)) {
      takeList(false);
      continue;
    }
    if (/^\s*\d+\.\s+/.test(raw)) {
      takeList(true);
      continue;
    }
    takeParagraph();
  }

  return blocks;
}

function StatWikiContent({
  tab,
  setTab,
  level,
  listResource,
}) {
  let lists;
  try {
    lists = listResource.read();
  } catch (e) {
    if (e?.then) throw e;
    return (
      <div className="max-w-[1400px]">
        <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-tertiary)] text-sm text-[color:var(--text-secondary)]">
          {e?.message || 'Не удалось загрузить справочник'}
        </div>
      </div>
    );
  }

  return (
    <StatWikiContentLoaded
      tab={tab}
      setTab={setTab}
      level={level}
      lists={lists}
    />
  );
}

function StatWikiContentLoaded({
  tab,
  setTab,
  level,
  lists,
}) {
  const isManual = tab === 'manual';

  const manualResource = useMemo(() => {
    if (!isManual) return null;
    return createResource(() => getKnowledgeManual('ru'));
  }, [isManual]);

  const terms = useMemo(() => {
    return Array.isArray(lists?.termList) ? lists.termList : [];
  }, [lists]);

  const tests = useMemo(() => {
    return Array.isArray(lists?.testList) ? lists.testList : [];
  }, [lists]);

  const levelLabel = level === 'junior' ? 'Начальный' : level === 'mid' ? 'Средний' : 'Продвинутый';

  const TEST_CATEGORIES = useMemo(() => {
    return [
      { id: 'compare_2', title: 'Сравнение 2 групп', keys: new Set(['t_test_ind', 't_test_welch', 'welch_t_test', 'mann_whitney']) },
      { id: 'paired', title: 'Парные сравнения', keys: new Set(['t_test_rel', 'wilcoxon', 'mcnemar']) },
      { id: 'compare_3_plus', title: 'Сравнение 3+ групп', keys: new Set(['anova', 'anova_welch', 'welch_anova', 'kruskal', 'kruskal_wallis', 'rm_anova', 'friedman']) },
      { id: 'categorical', title: 'Категориальные данные', keys: new Set(['chi_square', 'fisher', 'fisher_exact', 'cochran_q']) },
      { id: 'correlation', title: 'Связи и корреляции', keys: new Set(['pearson', 'spearman', 'clustered_correlation']) },
      { id: 'models', title: 'Модели', keys: new Set(['linear_regression', 'logistic_regression', 'mixed_model', 'mixed_effects']) },
      { id: 'ml', title: 'ML / предсказание', keys: new Set(['random_forest', 'gradient_boosting', 'knn', 'svm', 'roc_analysis']) },
    ];
  }, []);

  const testsByCategory = useMemo(() => {
    const out = new Map();
    TEST_CATEGORIES.forEach((c) => out.set(c.id, []));
    out.set('other', []);

    tests.forEach((t) => {
      const match = TEST_CATEGORIES.find((c) => c.keys.has(t.key));
      const id = match ? match.id : 'other';
      out.get(id).push(t);
    });

    return out;
  }, [TEST_CATEGORIES, tests]);

  const navigateToTerm = (termKey) => {
    setTab('terms');
    const id = `term-${String(termKey || '').trim()}`;
    setTimeout(() => {
      const el = typeof document !== 'undefined' ? document.getElementById(id) : null;
      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 0);
  };

  return (
    <div className="max-w-[1400px]">
      <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Справочник</div>
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-3xl font-black tracking-tight text-[color:var(--text-primary)]">Мини‑вики</h1>
        <div className="text-xs font-mono text-[color:var(--text-muted)]">{levelLabel}</div>
      </div>
      <div className="mt-2 text-sm text-[color:var(--text-secondary)] leading-relaxed max-w-[900px]">
        Термины, методы и тесты: когда выбирать, как считать, как интерпретировать.
      </div>

      <div className="mt-8">
        <Tabs value={tab} onValueChange={(v) => setTab(v)}>
          <TabsList>
            <TabsTrigger value="terms">Определения</TabsTrigger>
            <TabsTrigger value="tests">Тесты по категориям</TabsTrigger>
            <TabsTrigger value="manual">Мануал</TabsTrigger>
          </TabsList>

          <TabsContent value="terms" className="pt-6">
            <div className="space-y-3">
              {terms.map((m) => (
                <StatWikiDetailsCard
                  key={m.key}
                  id={`term-${m.key}`}
                  kindLabel="Определение"
                  title={m.term_ru || m.term || m.key}
                  code={m.key}
                  emoji={m.emoji}
                >
                  <StatWikiInlineArticle kind="terms" itemKey={m.key} level={level} meta={m} onNavigateToTerm={navigateToTerm} />
                </StatWikiDetailsCard>
              ))}
              {terms.length === 0 ? (
                <div className="text-sm text-[color:var(--text-secondary)]">Ничего не найдено.</div>
              ) : null}
            </div>
          </TabsContent>

          <TabsContent value="tests" className="pt-6">
            <div className="space-y-8">
              {TEST_CATEGORIES.map((cat) => {
                const list = testsByCategory.get(cat.id) || [];
                if (!list.length) return null;
                return (
                  <section key={cat.id} className="space-y-3">
                    <div className="flex items-baseline justify-between gap-3">
                      <h2 className="text-xl font-black tracking-tight text-[color:var(--text-primary)]">{cat.title}</h2>
                      <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">{list.length}</div>
                    </div>
                    <div className="space-y-3">
                      {list.map((m) => (
                        <StatWikiDetailsCard
                          key={m.key}
                          id={`test-${m.key}`}
                          kindLabel="Тест"
                          title={m.name_ru || m.name || m.key}
                          code={m.key}
                          emoji={m.emoji}
                        >
                          <StatWikiInlineArticle kind="tests" itemKey={m.key} level={level} meta={m} onNavigateToTerm={navigateToTerm} />
                        </StatWikiDetailsCard>
                      ))}
                    </div>
                  </section>
                );
              })}

              {(testsByCategory.get('other') || []).length ? (
                <section className="space-y-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <h2 className="text-xl font-black tracking-tight text-[color:var(--text-primary)]">Другое</h2>
                    <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">{(testsByCategory.get('other') || []).length}</div>
                  </div>
                  <div className="space-y-3">
                    {(testsByCategory.get('other') || []).map((m) => (
                      <StatWikiDetailsCard
                        key={m.key}
                        id={`test-${m.key}`}
                        kindLabel="Тест"
                        title={m.name_ru || m.name || m.key}
                        code={m.key}
                        emoji={m.emoji}
                      >
                        <StatWikiInlineArticle kind="tests" itemKey={m.key} level={level} meta={m} onNavigateToTerm={navigateToTerm} />
                      </StatWikiDetailsCard>
                    ))}
                  </div>
                </section>
              ) : null}

              {tests.length === 0 ? (
                <div className="text-sm text-[color:var(--text-secondary)]">Ничего не найдено.</div>
              ) : null}
            </div>
          </TabsContent>

          <TabsContent value="manual" className="pt-6">
            <div className="border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] overflow-hidden">
              <div className="px-5 py-4 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)]">
                <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">Мануал</div>
                <div className="mt-1 text-lg font-bold tracking-tight text-[color:var(--text-primary)]">Руководство пользователя</div>
              </div>
              <div className="px-5 py-5">
                <React.Suspense fallback={<div className="text-sm text-[color:var(--text-secondary)]">Загрузка мануала…</div>}>
                  <StatWikiManual manualResource={manualResource} />
                </React.Suspense>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

function StatWikiDetailsCard({ id, kindLabel, title, code, emoji, children }) {
  const [open, setOpen] = useState(false);

  return (
    <details
      id={id}
      className="border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] overflow-hidden"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary className="px-5 py-4 cursor-pointer list-none select-none">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">{kindLabel}</div>
            <div className="mt-1 text-lg font-bold tracking-tight text-[color:var(--text-primary)] truncate">{title}</div>
            <div className="mt-1 text-xs font-mono text-[color:var(--text-muted)] truncate">{code}</div>
          </div>
          <div className="text-xl" aria-hidden="true">{emoji}</div>
        </div>
      </summary>

      {open ? (
        <div className="px-5 py-5 border-t border-[color:var(--border-color)]">
          {children}
        </div>
      ) : null}
    </details>
  );
}

function StatWikiInlineArticle({ kind, itemKey, level, meta, onNavigateToTerm }) {
  const stableKey = String(itemKey || '').trim();

  const itemResource = useMemo(() => {
    return createResource(() => {
      return kind === 'tests'
        ? getKnowledgeTest(stableKey, { level })
        : getKnowledgeTerm(stableKey, level);
    });
  }, [kind, stableKey, level]);

  return (
    <React.Suspense fallback={<div className="text-sm text-[color:var(--text-secondary)]">Загрузка статьи…</div>}>
      <StatWikiArticle
        tab={kind}
        level={level}
        itemResource={itemResource}
        meta={meta}
        onNavigateToTerm={onNavigateToTerm}
      />
    </React.Suspense>
  );
}

function StatWikiManual({ manualResource }) {
  if (!manualResource) {
    return (
      <div className="text-sm text-[color:var(--text-secondary)]">Загрузка мануала…</div>
    );
  }

  let data;
  try {
    data = manualResource.read();
  } catch (e) {
    if (e?.then) throw e;
    return (
      <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-tertiary)] text-sm text-[color:var(--text-secondary)]">
        {e?.message || 'Не удалось загрузить мануал'}
      </div>
    );
  }

  const blocks = renderMarkdownBlocks(data?.markdown || '');

  return (
    <article className="max-w-[900px]">
      <div className="space-y-4 text-[15px] leading-relaxed text-[color:var(--text-primary)]">
        {blocks.map((b) => {
          if (b.type === 'h') {
            const Tag = b.depth === 1 ? 'h2' : b.depth === 2 ? 'h3' : 'h4';
            const cls = b.depth === 1
              ? 'text-2xl font-black tracking-tight'
              : b.depth === 2
                ? 'text-lg font-bold tracking-tight'
                : 'text-base font-bold';
            return <Tag key={b.key} className={cls}>{b.text}</Tag>;
          }
          if (b.type === 'p') return <p key={b.key}>{b.text}</p>;
          if (b.type === 'ul') {
            return (
              <ul key={b.key} className="pl-5 list-disc space-y-1 text-[color:var(--text-secondary)]">
                {b.items.map((x, idx) => <li key={idx}>{x}</li>)}
              </ul>
            );
          }
          if (b.type === 'ol') {
            return (
              <ol key={b.key} className="pl-5 list-decimal space-y-1 text-[color:var(--text-secondary)]">
                {b.items.map((x, idx) => <li key={idx}>{x}</li>)}
              </ol>
            );
          }
          if (b.type === 'code') {
            return (
              <pre key={b.key} className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-tertiary)] overflow-auto">
                <code className="font-mono text-xs text-[color:var(--text-primary)] whitespace-pre">{b.text}</code>
              </pre>
            );
          }
          return null;
        })}
      </div>
    </article>
  );
}

function StatWikiArticle({ tab, level, itemResource, meta, onNavigateToTerm }) {
  let selected;
  try {
    selected = itemResource?.read?.() || null;
  } catch (e) {
    if (e?.then) throw e;
    return (
      <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-tertiary)] text-sm text-[color:var(--text-secondary)]">
        {e?.message || 'Не удалось загрузить статью'}
      </div>
    );
  }

  const bodyParagraphs = tab === 'tests' ? splitParagraphs(selected?.why_it_works) : splitParagraphs(selected?.definition);
  const bullets = tab === 'tests'
    ? {
      when: Array.isArray(selected?.when_to_use) ? selected.when_to_use : [],
      assumptions: Array.isArray(selected?.assumptions) ? selected.assumptions : [],
      alt: normalizeAlternatives(selected?.alternatives),
      assumptionDetails: Array.isArray(selected?.assumption_details) ? selected.assumption_details : [],
      refs: Array.isArray(selected?.references) ? selected.references : [],
    }
    : {
      mistakes: Array.isArray(selected?.common_mistakes) ? selected.common_mistakes : [],
      checks: Array.isArray(selected?.what_to_check) ? selected.what_to_check : [],
      formula: selected?.formula ? String(selected.formula) : '',
      howToCheck: selected?.how_to_check ? String(selected.how_to_check) : '',
      ifViolated: selected?.if_violated ? String(selected.if_violated) : '',
      thresholds: selected?.thresholds && typeof selected.thresholds === 'object' ? selected.thresholds : null,
      methods: selected?.methods && typeof selected.methods === 'object' ? selected.methods : null,
      examples: Array.isArray(selected?.examples) ? selected.examples : [],
    };

  const title = pickTitle(meta, tab) || pickTitle(selected, tab) || '';
  const levelLabel = level === 'junior' ? 'Начальный' : level === 'mid' ? 'Средний' : 'Продвинутый';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-8 items-start">
      <div className="min-w-0">
        {bodyParagraphs.length > 0 ? (
          <div className="space-y-4 text-[15px] leading-relaxed text-[color:var(--text-primary)]">
            {bodyParagraphs.map((p, idx) => (
              <p key={idx}>{p}</p>
            ))}
          </div>
        ) : (
          <div className="text-sm text-[color:var(--text-secondary)]">Нет текста для отображения.</div>
        )}

        {tab === 'terms' && bullets.formula ? (
          <div className="mt-8 border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--bg-tertiary)]">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Формула</div>
            <div className="mt-3 font-mono text-sm text-[color:var(--text-primary)] whitespace-pre-wrap">{bullets.formula}</div>
          </div>
        ) : null}

        {tab === 'terms' && (bullets.howToCheck || bullets.ifViolated) ? (
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
            {bullets.howToCheck ? (
              <div className="border border-[color:var(--border-color)] rounded-[2px] p-5">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Как проверить</div>
                <div className="mt-3 text-sm text-[color:var(--text-primary)] leading-relaxed whitespace-pre-wrap">{bullets.howToCheck}</div>
              </div>
            ) : null}
            {bullets.ifViolated ? (
              <div className="border border-[color:var(--border-color)] rounded-[2px] p-5">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Если не выполняется</div>
                <div className="mt-3 text-sm text-[color:var(--text-primary)] leading-relaxed whitespace-pre-wrap">{bullets.ifViolated}</div>
              </div>
            ) : null}
          </div>
        ) : null}

        {tab === 'terms' && bullets.examples.length > 0 ? (
          <div className="mt-8">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Примеры</div>
            <div className="mt-3 grid grid-cols-1 gap-3">
              {bullets.examples.slice(0, 6).map((x, idx) => (
                <div key={idx} className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-tertiary)]">
                  <div className="text-sm text-[color:var(--text-primary)] leading-relaxed whitespace-pre-wrap">{String(x)}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {tab === 'terms' && bullets.mistakes.length > 0 ? (
          <div className="mt-8">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Частые ошибки</div>
            <ul className="mt-3 space-y-2 text-sm text-[color:var(--text-secondary)]">
              {bullets.mistakes.map((m, idx) => (
                <li key={idx} className="flex gap-3"><span className="font-mono text-[color:var(--text-muted)]">—</span><span>{String(m)}</span></li>
              ))}
            </ul>
          </div>
        ) : null}

        {tab === 'tests' && bullets.alt.length > 0 ? (
          <div className="mt-8">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Альтернативы (если допущения не проходят)</div>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
              {bullets.alt.slice(0, 6).map((x) => (
                <div key={x.key} className="border border-[color:var(--border-color)] rounded-[2px] p-4">
                  <div className="text-xs font-semibold text-[color:var(--text-primary)]">{x.title}</div>
                  <div className="mt-2 space-y-1">
                    {x.body.map((row, idx) => (
                      <div key={idx} className="text-sm text-[color:var(--text-secondary)] leading-relaxed">
                        {row.k ? <span className="font-mono text-[11px] text-[color:var(--text-muted)]">{row.k}: </span> : null}
                        <span>{row.v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {tab === 'tests' && bullets.assumptionDetails.length > 0 ? (
          <div className="mt-8">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Допущения: что это и как проверять</div>
            <div className="mt-3 grid grid-cols-1 gap-3">
              {bullets.assumptionDetails.slice(0, 12).map((a) => (
                <div key={String(a?.key || Math.random())} className="border border-[color:var(--border-color)] rounded-[2px] p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="text-sm font-black text-[color:var(--text-primary)] truncate">{String(a?.term_ru || a?.term || a?.key || '—')}</div>
                      <div className="mt-1 text-[11px] font-mono text-[color:var(--text-muted)] truncate">{String(a?.key || '')}</div>
                    </div>
                    {a?.key && typeof onNavigateToTerm === 'function' ? (
                      <button
                        type="button"
                        className="h-8 px-3 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-black tracking-widest text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)] transition-colors"
                        onClick={() => onNavigateToTerm(String(a.key))}
                      >
                        термин
                      </button>
                    ) : null}
                  </div>
                  {a?.definition ? (
                    <div className="mt-3 text-sm text-[color:var(--text-primary)] leading-relaxed whitespace-pre-wrap">{String(a.definition)}</div>
                  ) : null}
                  {a?.how_to_check ? (
                    <div className="mt-4 text-sm text-[color:var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
                      <span className="font-mono text-[11px] text-[color:var(--text-muted)]">как проверить: </span>
                      {String(a.how_to_check)}
                    </div>
                  ) : null}
                  {a?.if_violated ? (
                    <div className="mt-3 text-sm text-[color:var(--text-secondary)] leading-relaxed whitespace-pre-wrap">
                      <span className="font-mono text-[11px] text-[color:var(--text-muted)]">если не проходит: </span>
                      {String(a.if_violated)}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {tab === 'tests' && bullets.refs.length > 0 ? (
          <div className="mt-8">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Ссылки</div>
            <div className="mt-3 grid grid-cols-1 gap-3">
              {bullets.refs.slice(0, 6).map((r, idx) => {
                const citation = String(r?.citation || '').trim();
                const note = String(r?.note || '').trim();
                const url = String(r?.url || '').trim();
                const doiUrl = formatDoi(r?.doi);
                return (
                  <div key={String(r?.key || idx)} className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--bg-tertiary)]">
                    {citation ? <div className="text-sm text-[color:var(--text-primary)] leading-relaxed">{citation}</div> : null}
                    {note ? <div className="mt-2 text-xs text-[color:var(--text-muted)] leading-relaxed">{note}</div> : null}
                    {(doiUrl || url) ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {doiUrl ? (
                          <a className="text-xs font-mono text-[color:var(--accent)] hover:underline" href={doiUrl} target="_blank" rel="noreferrer">doi</a>
                        ) : null}
                        {url ? (
                          <a className="text-xs font-mono text-[color:var(--accent)] hover:underline" href={url} target="_blank" rel="noreferrer">url</a>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>

      <div className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--white)]">
        <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{tab === 'tests' ? 'Тест' : 'Термин'} · {levelLabel}</div>
        <div className="mt-3 text-sm font-black text-[color:var(--text-primary)] truncate">{title || '—'}</div>

        {tab === 'tests' ? (
          <div className="mt-5 space-y-5">
            <div>
              <div className="text-xs font-semibold text-[color:var(--text-secondary)]">Когда выбирать</div>
              {bullets.when.length ? (
                <ul className="mt-2 space-y-2 text-sm text-[color:var(--text-primary)]">
                  {bullets.when.slice(0, 6).map((x, idx) => (
                    <li key={idx} className="flex gap-3"><span className="font-mono text-[color:var(--text-muted)]">→</span><span>{String(x)}</span></li>
                  ))}
                </ul>
              ) : (
                <div className="mt-2 text-sm text-[color:var(--text-secondary)]">—</div>
              )}
            </div>

            <div>
              <div className="text-xs font-semibold text-[color:var(--text-secondary)]">Допущения</div>
              {bullets.assumptions.length ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {bullets.assumptions.slice(0, 10).map((x, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => (typeof onNavigateToTerm === 'function' ? onNavigateToTerm(String(x)) : null)}
                      className="inline-flex items-center h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] text-[11px] font-semibold text-[color:var(--text-secondary)] font-mono hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)] transition-colors"
                    >
                      {String(x)}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="mt-2 text-sm text-[color:var(--text-secondary)]">—</div>
              )}
            </div>
          </div>
        ) : (
          <div className="mt-5">
            <div className="text-xs font-semibold text-[color:var(--text-secondary)]">Проверить ещё</div>
            {bullets.checks.length ? (
              <ul className="mt-2 space-y-2 text-sm text-[color:var(--text-primary)]">
                {bullets.checks.slice(0, 8).map((x, idx) => (
                  <li key={idx} className="flex gap-3"><span className="font-mono text-[color:var(--text-muted)]">→</span><span>{String(x)}</span></li>
                ))}
              </ul>
            ) : (
              <div className="mt-2 text-sm text-[color:var(--text-secondary)]">—</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
