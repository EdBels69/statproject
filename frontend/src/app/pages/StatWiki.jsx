import React, { useMemo, useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs';
import Input from '../components/ui/Input';
import { useLanguage } from '../../contexts/LanguageContext';
import { getKnowledgeTerm, getKnowledgeTerms, getKnowledgeTest, getKnowledgeTests } from '../../lib/api';

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
  const [query, setQuery] = useState('');
  const [levelOverride, setLevelOverride] = useState(null);
  const [selectedKey, setSelectedKey] = useState(null);

  const level = levelOverride ?? (educationLevel || 'junior');

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
        query={query}
        setQuery={setQuery}
        level={level}
        levelOverride={levelOverride}
        setLevelOverride={setLevelOverride}
        selectedKey={selectedKey}
        setSelectedKey={setSelectedKey}
        listResource={listResource}
      />
    </React.Suspense>
  );
}

function StatWikiContent({
  tab,
  setTab,
  query,
  setQuery,
  level,
  levelOverride,
  setLevelOverride,
  selectedKey,
  setSelectedKey,
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
      query={query}
      setQuery={setQuery}
      level={level}
      levelOverride={levelOverride}
      setLevelOverride={setLevelOverride}
      selectedKey={selectedKey}
      setSelectedKey={setSelectedKey}
      lists={lists}
    />
  );
}

function StatWikiContentLoaded({
  tab,
  setTab,
  query,
  setQuery,
  level,
  levelOverride,
  setLevelOverride,
  selectedKey,
  setSelectedKey,
  lists,
}) {
  const terms = lists?.termList || [];
  const tests = lists?.testList || [];

  const activeList = tab === 'tests' ? tests : terms;

  const filtered = useMemo(() => {
    const q = String(query || '').trim().toLowerCase();
    if (!q) return activeList;
    return activeList.filter((x) => {
      const title = pickTitle(x, tab).toLowerCase();
      return title.includes(q) || x.key.toLowerCase().includes(q);
    });
  }, [activeList, query, tab]);

  const effectiveSelectedKey = selectedKey && activeList.some((x) => x.key === selectedKey)
    ? selectedKey
    : (filtered[0]?.key || null);

  const selectedMeta = useMemo(() => {
    return activeList.find((x) => x.key === effectiveSelectedKey) || null;
  }, [activeList, effectiveSelectedKey]);

  const itemResource = useMemo(() => {
    if (!effectiveSelectedKey) return null;
    return createResource(() => {
      return tab === 'tests'
        ? getKnowledgeTest(effectiveSelectedKey, { level })
        : getKnowledgeTerm(effectiveSelectedKey, level);
    });
  }, [effectiveSelectedKey, tab, level]);

  const levelLabel = level === 'junior' ? 'Начальный' : level === 'mid' ? 'Средний' : 'Продвинутый';

  return (
    <div className="max-w-[1400px]">
      <div className="grid grid-cols-1 xl:grid-cols-[420px_1fr] gap-8 items-start">
        <div className="sticky top-20">
          <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Справочник</div>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-[color:var(--text-primary)]">Мини‑вики</h1>
          <div className="mt-2 text-sm text-[color:var(--text-secondary)] leading-relaxed">
            Термины, методы и тесты: когда выбирать, как считать, как интерпретировать.
          </div>

          <div className="mt-6 grid grid-cols-1 gap-3">
            <label className="grid gap-1">
              <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Глубина</div>
              <select
                value={levelOverride ?? level}
                onChange={(e) => setLevelOverride(e.target.value)}
                className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                aria-label="Глубина объяснений"
              >
                <option value="junior">Начальный</option>
                <option value="mid">Средний</option>
                <option value="senior">Продвинутый</option>
              </select>
            </label>

            <label className="grid gap-1">
              <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Поиск</div>
              <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="p-value, ANOVA, нормальность…" />
            </label>
          </div>

          <div className="mt-8">
            <Tabs
              value={tab}
              onValueChange={(v) => {
                setTab(v);
                setQuery('');
                setSelectedKey(null);
              }}
            >
              <TabsList>
                <TabsTrigger value="terms">Термины</TabsTrigger>
                <TabsTrigger value="tests">Тесты</TabsTrigger>
              </TabsList>

              <TabsContent value="terms" className="pt-5">
                <div className="border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] overflow-hidden">
                  <div className="px-4 py-3 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)]">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Список</div>
                  </div>
                  <div className="max-h-[520px] overflow-auto">
                    {filtered.map((x) => {
                      const active = x.key === effectiveSelectedKey;
                      return (
                        <button
                          key={x.key}
                          type="button"
                          onClick={() => setSelectedKey(x.key)}
                          className={`w-full text-left px-4 py-3 border-b border-[color:var(--border-color)] transition ${active ? 'bg-[color:var(--bg-tertiary)]' : 'hover:bg-[color:var(--bg-secondary)]'}`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <div className={`text-sm font-semibold truncate ${active ? 'text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)]'}`}>{x.term_ru || x.term || x.key}</div>
                              <div className="mt-0.5 text-[10px] text-[color:var(--text-muted)] font-mono truncate">{x.key}</div>
                            </div>
                            <div className="text-lg" aria-hidden="true">{x.emoji}</div>
                          </div>
                        </button>
                      );
                    })}
                    {filtered.length === 0 ? (
                      <div className="px-4 py-4 text-sm text-[color:var(--text-secondary)]">Ничего не найдено.</div>
                    ) : null}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="tests" className="pt-5">
                <div className="border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] overflow-hidden">
                  <div className="px-4 py-3 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)]">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Список</div>
                  </div>
                  <div className="max-h-[520px] overflow-auto">
                    {filtered.map((x) => {
                      const active = x.key === effectiveSelectedKey;
                      return (
                        <button
                          key={x.key}
                          type="button"
                          onClick={() => setSelectedKey(x.key)}
                          className={`w-full text-left px-4 py-3 border-b border-[color:var(--border-color)] transition ${active ? 'bg-[color:var(--bg-tertiary)]' : 'hover:bg-[color:var(--bg-secondary)]'}`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <div className={`text-sm font-semibold truncate ${active ? 'text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)]'}`}>{x.name_ru || x.name || x.key}</div>
                              <div className="mt-0.5 text-[10px] text-[color:var(--text-muted)] font-mono truncate">{x.key}</div>
                            </div>
                            <div className="text-lg" aria-hidden="true">{x.emoji}</div>
                          </div>
                        </button>
                      );
                    })}
                    {filtered.length === 0 ? (
                      <div className="px-4 py-4 text-sm text-[color:var(--text-secondary)]">Ничего не найдено.</div>
                    ) : null}
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>

        <div>
          <div className="card overflow-hidden">
            <div className="px-6 py-5 border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
              <div className="flex items-start justify-between gap-6">
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{tab === 'tests' ? 'Тест' : 'Термин'} · {levelLabel}</div>
                  <div className="mt-2 text-2xl font-black tracking-tight text-[color:var(--text-primary)] truncate">{pickTitle(selectedMeta, tab) || '—'}</div>
                </div>
                <div className="text-right">
                  <div className="text-[11px] font-semibold text-[color:var(--text-secondary)]">id</div>
                  <div className="font-mono text-sm text-[color:var(--text-muted)]">{effectiveSelectedKey || '—'}</div>
                </div>
              </div>
            </div>

            <div className="px-6 py-6 bg-[color:var(--white)]">
              {!effectiveSelectedKey ? (
                <div className="text-sm text-[color:var(--text-secondary)]">Выберите пункт слева.</div>
              ) : (
                <React.Suspense fallback={<div className="text-sm text-[color:var(--text-secondary)]">Загрузка статьи…</div>}>
                  <StatWikiArticle
                    tab={tab}
                    level={level}
                    itemResource={itemResource}
                    meta={selectedMeta}
                    onNavigateToTerm={(termKey) => {
                      setTab('terms');
                      setQuery('');
                      setSelectedKey(termKey);
                    }}
                  />
                </React.Suspense>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
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
