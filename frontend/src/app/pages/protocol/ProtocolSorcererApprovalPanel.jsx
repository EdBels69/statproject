import Badge from '../../components/ui/Badge';
import Button from '../../components/ui/Button';

export default function ProtocolSorcererApprovalPanel({
  approved,
  onResetChat,
  onApprove,
  approveDisabled,
  prepSummary,
  prepNormalizeCol,
  onPrepNormalizeColChange,
  prepBusy,
  selectedDatasetId,
  prepCategoricalColumns,
  prepInfoByName,
  onOpenPrep,
  onPrepNormalizeCategories,
  prepError,
  contractIssues,
  hasChatProtocol,
  recommendationMethodId,
  aiContextLoading,
  aiContextSummary,
  chatText,
  onChatTextChange,
  chatError,
  onChatSend,
  chatBusy,
  chatProtocol,
  chatNotes,
}) {
  const protocolSteps = Array.isArray(chatProtocol) ? chatProtocol : [];
  const issues = Array.isArray(contractIssues) ? contractIssues : [];
  const notes = Array.isArray(chatNotes) ? chatNotes : [];

  return (
    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-6">
      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div className="min-w-0">
          <div className="text-[10px] font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Согласование дизайна</div>
          <div className="mt-2 text-sm text-[color:var(--text-secondary)] max-w-2xl">
            Опишите дизайн исследования человеческим языком — ИИ соберёт черновик протокола. Запуск доступен только после approve.
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className={approved ? 'px-3 py-2 rounded-[999px] bg-[color:var(--accent)] text-[color:var(--white)] text-xs font-black tracking-widest' : 'px-3 py-2 rounded-[999px] border border-[color:var(--border-color)] text-xs font-black tracking-widest text-[color:var(--text-secondary)]'}>
            {approved ? 'СОГЛАСОВАНО' : 'НЕ СОГЛАСОВАНО'}
          </div>
          <Button
            variant="ghost"
            onClick={onResetChat}
            className="px-4"
          >
            Сбросить
          </Button>
          <Button
            variant="primary"
            onClick={onApprove}
            disabled={approveDisabled}
            className="px-6"
          >
            Approve
          </Button>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-7 border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-secondary)]">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[10px] font-black text-[color:var(--text-primary)] uppercase tracking-wide">Prep-чеклист</div>
            <div className="flex items-center gap-2 flex-wrap justify-end">
              <Badge variant={prepSummary?.missingCols ? 'accent' : 'neutral'}>ПРОПУСКИ · {prepSummary?.missingCols ?? 0}</Badge>
              <Badge variant={prepSummary?.constantCols ? 'accent' : 'neutral'}>КОНСТАНТЫ · {prepSummary?.constantCols ?? 0}</Badge>
              <Badge variant="neutral">КАТЕГОРИИ · {prepSummary?.categoricalCols ?? 0}</Badge>
            </div>
          </div>
          <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
            Быстро выровняйте орфографию/регистр/пробелы в категориях, затем переходите к полноценной подготовке.
          </div>

          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
            <div className="md:col-span-2">
              <div className="text-[10px] font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Нормализация категорий</div>
              <select
                className="mt-2 w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                value={prepNormalizeCol}
                onChange={(e) => onPrepNormalizeColChange?.(e.target.value)}
                disabled={prepBusy || !selectedDatasetId}
              >
                <option value="">-- Выберите колонку --</option>
                {prepCategoricalColumns.map((name) => {
                  const info = prepInfoByName?.get?.(String(name));
                  const uniq = typeof info?.unique_count === 'number' && Number.isFinite(info.unique_count) ? info.unique_count : null;
                  const miss = typeof info?.missing_count === 'number' && Number.isFinite(info.missing_count) ? info.missing_count : null;
                  const suffix = [
                    uniq != null ? `уник. ${uniq}` : null,
                    miss != null ? `проп. ${miss}` : null,
                  ].filter(Boolean).join(' · ');

                  return (
                    <option key={String(name)} value={String(name)}>
                      {String(name)}{suffix ? ` — ${suffix}` : ''}
                    </option>
                  );
                })}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                onClick={onOpenPrep}
                disabled={!selectedDatasetId || prepBusy}
                className="px-4"
              >
                Подготовка →
              </Button>
              <Button
                variant="primary"
                onClick={onPrepNormalizeCategories}
                disabled={prepBusy || !selectedDatasetId || !String(prepNormalizeCol || '').trim()}
                className="px-5"
              >
                {prepBusy ? 'Обрабатываю…' : 'Нормализовать'}
              </Button>
            </div>
          </div>
          {prepError ? (
            <div className="mt-3 text-xs font-semibold text-[color:var(--accent)]">{String(prepError)}</div>
          ) : null}
        </div>

        <div className="lg:col-span-5 border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[10px] font-black text-[color:var(--text-primary)] uppercase tracking-wide">Контракт</div>
            <Badge variant={issues.length ? 'error' : 'success'}>
              {issues.length ? `ПРОБЛЕМЫ · ${issues.length}` : 'OK'}
            </Badge>
          </div>

          {issues.length ? (
            <div className="mt-3 space-y-1">
              {issues.slice(0, 8).map((it, idx) => (
                <div key={idx} className="text-[11px] font-mono text-[color:var(--text-secondary)] break-words">
                  — {String(it)}
                </div>
              ))}
              {issues.length > 8 ? (
                <div className="pt-1 text-[11px] font-mono text-[color:var(--text-muted)]">
                  …и ещё {issues.length - 8}
                </div>
              ) : null}
              <div className="pt-2 text-xs text-[color:var(--text-secondary)]">Approve заблокирован, пока не исправите обязательные поля.</div>
            </div>
          ) : (
            <div className="mt-3 text-sm text-[color:var(--text-secondary)]">
              Контракт согласования чист. Можно approve и запускать.
            </div>
          )}

          {!hasChatProtocol && recommendationMethodId === 'consult_statistician' ? (
            <div className="mt-3 text-xs text-[color:var(--text-secondary)]">
              Выбран вариант «Консультация статистика» — протокол запуска не требуется.
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-secondary)]">
          <div className="text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Чат</div>
          <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
            Пример: «3 группы, исход — выписан/нет, хотим сравнить доли, поправка на множественность не нужна».
          </div>
          <details className="mt-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2">
            <summary className="cursor-pointer text-[11px] font-semibold text-[color:var(--text-primary)]">
              Что видит ИИ (метаданные)
            </summary>
            <div className="mt-2 text-[11px] text-[color:var(--text-secondary)] space-y-1">
              {aiContextLoading ? (
                <div>Загружаю метаданные…</div>
              ) : (
                <>
                  <div>Строк: {aiContextSummary?.rows ?? '—'} · Колонок: {aiContextSummary?.cols ?? '—'}</div>
                  <div>Числовых: {aiContextSummary?.numericCount ?? '—'} · Категорий: {aiContextSummary?.catCount ?? '—'}</div>
                  <div>
                    Группа: {aiContextSummary?.groupCol || '—'} · Время: {aiContextSummary?.timeCol || '—'} · Субъект: {aiContextSummary?.subjectCol || '—'}
                  </div>
                </>
              )}
            </div>
          </details>
          <textarea
            value={chatText}
            onChange={(e) => onChatTextChange?.(e.target.value)}
            placeholder="Опишите дизайн…"
            className="mt-3 w-full min-h-[120px] border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] text-sm focus:border-[color:var(--accent)] focus:outline-none"
          />
          {chatError ? (
            <div className="mt-2 text-xs font-semibold text-[color:var(--accent)]">{String(chatError)}</div>
          ) : null}
          <div className="mt-3 flex items-center justify-between gap-3">
            <Button
              variant="ghost"
              onClick={onOpenPrep}
              disabled={!selectedDatasetId}
              className="px-4"
            >
              Подготовка данных
            </Button>
            <Button
              variant="primary"
              onClick={onChatSend}
              disabled={chatBusy || !selectedDatasetId || !String(chatText || '').trim()}
              className="px-6"
            >
              {chatBusy ? 'Думаю…' : 'Собрать протокол'}
            </Button>
          </div>
        </div>

        <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Черновик протокола</div>
            <div className="text-xs font-mono text-[color:var(--text-secondary)]">
              {protocolSteps.length ? `${protocolSteps.length} шаг(ов)` : '—'}
            </div>
          </div>

          {protocolSteps.length ? (
            <div className="mt-3 space-y-2">
              {protocolSteps.slice(0, 12).map((s, idx) => (
                <div key={String(s?.id || idx)} className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs font-black text-[color:var(--text-primary)] truncate">
                      {String(s?.name || s?.method || 'Шаг')}
                    </div>
                    <div className="text-[11px] font-mono text-[color:var(--text-secondary)]">{String(s?.method || '')}</div>
                  </div>
                  {s?.config && typeof s.config === 'object' ? (
                    <div className="mt-1 text-[11px] font-mono text-[color:var(--text-secondary)] break-words">
                      {Object.entries(s.config)
                        .filter(([, v]) => v !== null && v !== undefined && String(v) !== '')
                        .slice(0, 4)
                        .map(([k, v]) => `${k}=${String(v)}`)
                        .join(' · ')}
                    </div>
                  ) : null}
                </div>
              ))}
              {notes.length ? (
                <div className="mt-3 border-l-2 border-[color:var(--accent)] pl-3 py-2 bg-[color:var(--bg-secondary)]">
                  <div className="text-[10px] font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Примечания</div>
                  <div className="mt-2 space-y-1">
                    {notes.slice(0, 6).map((n, i) => (
                      <div key={i} className="text-xs text-[color:var(--text-primary)]">{String(n)}</div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="mt-4 text-sm text-[color:var(--text-secondary)]">
              Пока пусто. Напишите дизайн и нажмите «Собрать протокол».
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
