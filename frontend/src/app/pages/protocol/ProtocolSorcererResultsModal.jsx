import { Suspense } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Button from '../../components/ui/Button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../../components/ui/Table';
import { StatTooltip } from '../../components/education';
import { useTranslation } from '../../../hooks/useTranslation';
import VisualizationFactory from '../../components/visualizations/VisualizationFactory';

const MotionDiv = motion.div;

const AIProvenanceDetails = ({ meta }) => {
  const { t } = useTranslation();
  const rule = meta?.rule && typeof meta.rule === 'string' ? meta.rule : null;
  const facts = meta?.facts && typeof meta.facts === 'object' && !Array.isArray(meta.facts) ? meta.facts : null;
  const constraints = Array.isArray(meta?.constraints) ? meta.constraints.filter(Boolean).map(String) : [];

  const factEntries = facts
    ? Object.entries(facts)
      .filter(([k, v]) => k && v !== undefined && v !== null && String(k).trim())
      .sort(([a], [b]) => String(a).localeCompare(String(b)))
    : [];

  if (!rule && factEntries.length === 0 && constraints.length === 0) return null;

  const labelForFact = (k) => {
    const key = `ai_fact_${String(k)}`;
    const label = t(key);
    return label === key ? String(k) : label;
  };

  const labelForConstraint = (k) => {
    const key = `ai_constraint_${String(k)}`;
    const label = t(key);
    return label === key ? String(k) : label;
  };

  const renderValue = (v) => {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'boolean') return v ? t('yes') : t('no');
    if (typeof v === 'number') return Number.isFinite(v) ? String(v) : '—';
    if (Array.isArray(v)) return v.map((x) => String(x)).join(' — ');
    if (typeof v === 'object') return JSON.stringify(v, null, 2);
    return String(v);
  };

  return (
    <details className="mt-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-3">
      <summary className="cursor-pointer select-none text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
        {t('ai_why')}
      </summary>
      <div className="mt-3 space-y-4">
        {rule ? (
          <div className="text-[10px] font-mono text-[color:var(--text-secondary)]">{String(rule)}</div>
        ) : null}

        {factEntries.length > 0 ? (
          <div>
            <div className="text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)]">{t('ai_facts')}</div>
            <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2">
              {factEntries.map(([k, v]) => (
                <div key={String(k)} className="flex items-start justify-between gap-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2">
                  <div className="text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)]">{labelForFact(k)}</div>
                  <div className="text-[10px] font-mono text-[color:var(--text-primary)] text-right whitespace-pre-wrap break-words max-w-[56%]">{renderValue(v)}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {constraints.length > 0 ? (
          <div>
            <div className="text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)]">{t('ai_constraints')}</div>
            <div className="mt-2 space-y-1">
              {constraints.map((c) => (
                <div key={c} className="text-xs text-[color:var(--text-secondary)]">{labelForConstraint(c)}</div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </details>
  );
};

export default function ProtocolSorcererResultsModal({
  resultsOpen,
  onClose,
  selectedDataset,
  variables,
  resultsSections,
  setResultsSections,
  articleUi,
  setArticleUi,
  articleMetrics,
  setArticleMetrics,
  flatBatchItemsLength,
  batchSummary,
  topSignificantRows,
  articleRows,
  articleHasSlice,
  batchGroupNames,
  drilldownSort,
  setDrilldownSort,
  runDrilldown,
  inspector,
  setInspector,
  analysisResult,
  formatP,
  formatGroupCell,
  pClass,
  multiplicityLabel,
  postHocCorrectionLabel,
  postHocLabel,
  reportStyle,
  setReportStyle,
  reportDensity,
  setReportDensity,
  reportAccent,
  setReportAccent,
  handleDownloadReport,
  handleDownloadReportDocx,
  handleDownloadReportHtml,
  reset,
  chartFallback,
  AnalyticsChart: AnalyticsChartProp,
  drilldownResult,
  chartRef,
}) {
  const { t } = useTranslation();
  if (!resultsOpen) return null;

  const aiMeta = analysisResult?.ai_meta && typeof analysisResult.ai_meta === 'object' ? analysisResult.ai_meta : null;
  const aiSource = aiMeta?.source && typeof aiMeta.source === 'string' ? aiMeta.source : null;
  const aiText = analysisResult?.ai_interpretation || analysisResult?.conclusion;

  const postHocTerm = variables?.post_hoc === 'dunn' ? 'post_hoc_dunn' : (variables?.post_hoc === 'games_howell' ? 'post_hoc_games_howell' : (variables?.post_hoc === 'tukey' ? 'post_hoc_tukey' : 'post_hoc'));

  return (
    <AnimatePresence>
      <MotionDiv
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-3 md:p-6"
      >
        <div
          className="absolute inset-0 bg-black/50"
          onClick={onClose}
        />
        <div
          role="dialog"
          aria-modal="true"
          className="relative w-full max-w-6xl bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden"
        >
        <div className="px-6 py-4 border-b border-[color:var(--border-color)] flex items-center justify-between gap-6">
          <div>
            <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{t('results')}</div>
            <div className="mt-1 font-black text-[color:var(--text-primary)]">
              {selectedDataset?.filename ? selectedDataset.filename : selectedDataset?.id}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
            >
              {t('close')}
            </button>
          </div>
        </div>
        <div className="max-h-[calc(100vh-8rem)] overflow-y-auto p-6">
          <div className="space-y-8 animate-in fade-in duration-700">
            <div className="flex items-center gap-4">
              <div className="h-px flex-1 bg-[color:var(--border-color)]"></div>
              <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{t('results')}</div>
              <div className="h-px flex-1 bg-[color:var(--border-color)]"></div>
            </div>

            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setResultsSections((s) => ({ ...s, article: !s.article }))}
                  className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${resultsSections.article ? 'border-[color:var(--text-primary)] text-[color:var(--text-primary)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                >
                  {t('article')}
                </button>
                <button
                  type="button"
                  onClick={() => setResultsSections((s) => ({ ...s, details: !s.details }))}
                  className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${resultsSections.details ? 'border-[color:var(--text-primary)] text-[color:var(--text-primary)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                >
                  {t('details')}
                </button>
                <button
                  type="button"
                  onClick={() => setResultsSections((s) => ({ ...s, chart: !s.chart }))}
                  className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${resultsSections.chart ? 'border-[color:var(--accent)] text-[color:var(--text-primary)] bg-[color:var(--bg-secondary)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                >
                  {t('plot')}
                </button>
                <button
                  type="button"
                  onClick={() => setResultsSections((s) => ({ ...s, significant: !s.significant }))}
                  className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${resultsSections.significant ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                >
                  {t('significant')}
                </button>
              </div>
              <div className="text-xs font-mono text-[color:var(--text-secondary)]">
                α={Number.isFinite(Number(variables.alpha)) ? Number(variables.alpha).toFixed(3) : '0.050'}
              </div>
            </div>

            {resultsSections.article && flatBatchItemsLength > 0 && (
              <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                <div className="px-6 py-5 border-b border-[color:var(--border-color)]">
                  <div className="flex items-start justify-between gap-6 flex-wrap">
                    <div>
                      <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{t('article_table_title')}</div>
                      <div className="mt-2 text-sm text-[color:var(--text-secondary)]">
                        {batchSummary ? t('batch_summary', { total: batchSummary.total, significant: batchSummary.significant }) : t('batch_summary_unavailable')}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-wrap">
                      <input
                        value={articleUi.query}
                        onChange={(e) => setArticleUi((s) => ({ ...s, query: e.target.value }))}
                        placeholder={t('search_metric_placeholder')}
                        className="w-64 max-w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors text-sm"
                      />
                      <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                        <input
                          type="checkbox"
                          checked={articleUi.showSignificantOnly}
                          onChange={(e) => setArticleUi((s) => ({ ...s, showSignificantOnly: e.target.checked }))}
                          className="accent-[color:var(--accent)]"
                        />
                        {t('significant_only')}
                      </label>
                      <button
                        type="button"
                        onClick={() => setArticleUi((s) => ({ ...s, showColumns: !s.showColumns }))}
                        className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${articleUi.showColumns ? 'border-[color:var(--text-primary)] text-[color:var(--text-primary)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                      >
                        {t('columns')}
                      </button>
                    </div>
                  </div>

                  {articleUi.showColumns && (
                    <div className="mt-5 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)] p-4">
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        {([
                          ['n', 'n'],
                          ['mean', 'Mean'],
                          ['sd', 'SD'],
                          ['sem', 'SEM'],
                          ['median', 'Median'],
                          ['iqr', 'IQR'],
                          ['min', 'Min'],
                          ['max', 'Max'],
                          ['cv', 'CV'],
                          ['ci', 'CI95'],
                        ]).map(([key, label]) => (
                          <label key={key} className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                            <input
                              type="checkbox"
                              checked={Boolean(articleMetrics[key])}
                              onChange={(e) => setArticleMetrics((m) => ({ ...m, [key]: e.target.checked }))}
                              className="accent-[color:var(--accent)]"
                            />
                            {label}
                          </label>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {resultsSections.significant && topSignificantRows.length > 0 && (
                  <div className="px-6 py-4 border-b border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]">
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                      <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{t('quick_drilldown')}</div>
                      <div className="flex items-center gap-3">
                        <div className="text-xs font-mono text-[color:var(--text-secondary)]">top {topSignificantRows.length}</div>
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => setDrilldownSort('alpha')}
                            className={`h-7 px-2 rounded-[2px] border text-[10px] font-black uppercase tracking-widest transition-colors ${drilldownSort === 'alpha'
                              ? 'border-[color:var(--accent)] bg-[color:var(--white)] text-[color:var(--text-primary)]'
                              : 'border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]'}`}
                          >
                            A–Z
                          </button>
                          <button
                            type="button"
                            onClick={() => setDrilldownSort('slice')}
                            className={`h-7 px-2 rounded-[2px] border text-[10px] font-black uppercase tracking-widest transition-colors ${drilldownSort === 'slice'
                              ? 'border-[color:var(--accent)] bg-[color:var(--white)] text-[color:var(--text-primary)]'
                              : 'border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]'}`}
                          >
                            {t('sort_by_slice_button')}
                          </button>
                          <button
                            type="button"
                            onClick={() => setDrilldownSort('p')}
                            className={`h-7 px-2 rounded-[2px] border text-[10px] font-black uppercase tracking-widest transition-colors ${drilldownSort === 'p'
                              ? 'border-[color:var(--accent)] bg-[color:var(--white)] text-[color:var(--text-primary)]'
                              : 'border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]'}`}
                          >
                            p
                          </button>
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 overflow-x-auto">
                      <Table className="w-full text-sm">
                        <TableHeader className="text-[color:var(--text-secondary)]">
                          <TableRow className="border-b border-[color:var(--border-color)]">
                            {articleHasSlice && (
                              <TableHead className="py-2 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_slice')}</TableHead>
                            )}
                            <TableHead className="py-2 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_metric')}</TableHead>
                            <TableHead className="py-2 pr-4 text-left font-black uppercase tracking-widest text-xs">p</TableHead>
                            <TableHead className="py-2 text-left font-black uppercase tracking-widest text-xs">{t('header_actions')}</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {topSignificantRows.map((r) => (
                            <TableRow key={`${String(r.slice)}__${String(r.target)}`} className="border-b border-[color:var(--border-color)] last:border-b-0">
                              {articleHasSlice && (
                                <TableCell className="py-2 pr-4 text-[color:var(--text-secondary)]">{r.slice ?? '—'}</TableCell>
                              )}
                              <TableCell className="py-2 pr-4 font-bold text-[color:var(--text-primary)]">{r.target}</TableCell>
                              <TableCell className="py-2 pr-4 font-mono font-black text-[color:var(--text-primary)]">{formatP(r.pUsed)}</TableCell>
                              <TableCell className="py-2">
                                <button
                                  type="button"
                                  onClick={() => runDrilldown({ target: r.target, slice: r.slice })}
                                  className="px-3 py-2 rounded-[2px] border border-[color:var(--success)] text-[10px] font-black uppercase tracking-widest text-[color:var(--text-primary)] bg-[color:var(--white)] hover:bg-[color:var(--bg-secondary)] transition-colors"
                                >
                                  {t('plot')}
                                </button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                )}

                <div className="p-6 overflow-x-auto">
                  <Table className="w-full text-sm">
                    <TableHeader className="text-[color:var(--text-secondary)]">
                      <TableRow className="border-b border-[color:var(--border-color)]">
                        {articleHasSlice && (
                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_slice')}</TableHead>
                        )}
                        <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_metric')}</TableHead>
                        {batchGroupNames.map((g) => (
                          <TableHead key={String(g)} className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{g}</TableHead>
                        ))}
                        <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                          <StatTooltip term="p_value" level="junior" position="top">
                            <span>p</span>
                          </StatTooltip>
                        </TableHead>
                        <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                          <StatTooltip term="multiplicity_correction" level="junior" position="top">
                            <span>p({multiplicityLabel})</span>
                          </StatTooltip>
                        </TableHead>
                        <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_significant')}</TableHead>
                        <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">{t('header_actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {articleRows.map((row) => {
                        const inspectorKey = articleHasSlice
                          ? `${String(row.slice)}__${String(row.target)}`
                          : String(row.target);
                        return (
                          <TableRow key={inspectorKey} className="border-b border-[color:var(--border-color)] last:border-b-0">
                            {articleHasSlice && (
                              <TableCell className="py-3 pr-4 text-[color:var(--text-secondary)]">{row.slice ?? '—'}</TableCell>
                            )}
                            <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{row.target}</TableCell>
                            {batchGroupNames.map((g) => (
                              <TableCell key={`${inspectorKey}__${String(g)}`} className="py-3 pr-4 font-mono text-[color:var(--text-secondary)] whitespace-nowrap">
                                {formatGroupCell(row.item?.plot_stats?.[g])}
                              </TableCell>
                            ))}
                            <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(row.pRaw)}</TableCell>
                            <TableCell className={`py-3 pr-4 font-mono font-black ${pClass(row.pUsed)}`}>{formatP(row.pUsed)}</TableCell>
                            <TableCell className="py-3 pr-4">
                              <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${row.isSig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                {row.isSig ? t('yes') : t('no')}
                              </span>
                            </TableCell>
                            <TableCell className="py-3">
                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => {
                                    setResultsSections((s) => ({ ...s, details: true }));
                                    setInspector((prev) => (prev?.key === inspectorKey ? null : { key: inspectorKey, target: row.target, slice: row.slice, item: row.item }));
                                  }}
                                  className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                                >
                                  {t('details')}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => runDrilldown({ target: row.target, slice: row.slice })}
                                  className="px-3 py-2 rounded-[2px] border border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-xs font-black uppercase tracking-widest text-[color:var(--text-primary)] hover:bg-[color:var(--white)] transition-colors"
                                >
                                  {t('plot')}
                                </button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>

                  {!articleRows.length && (
                    <div className="mt-4 text-sm text-[color:var(--text-secondary)]">{t('no_rows_for_filter')}</div>
                  )}
                </div>
              </div>
            )}

            <VisualizationFactory
              result={analysisResult}
              inspector={inspector}
              setInspector={setInspector}
              runDrilldown={runDrilldown}
              multiplicityLabel={multiplicityLabel}
              postHocLabel={postHocLabel}
              postHocCorrectionLabel={postHocCorrectionLabel}
              postHocTerm={postHocTerm}
              AnalyticsChart={AnalyticsChartProp}
              chartFallback={chartFallback}
            />

                <div className="flex justify-center mt-4 gap-3 flex-wrap">
                  <Button variant="secondary" onClick={handleDownloadReport} className="px-8">
                    <span>📥</span> {t('download_report_pdf')}
                  </Button>
                  <Button variant="ghost" onClick={handleDownloadReportDocx} className="px-8">
                    <span>⌁</span> {t('download_report_docx')}
                  </Button>
                  <Button variant="ghost" onClick={handleDownloadReportHtml} className="px-8">
                    {t('download_report_html')}
                  </Button>
                </div>

                <div className="flex justify-center mt-3 gap-2 flex-wrap items-center">
                  <div className="text-[10px] font-black uppercase tracking-widest text-[color:var(--text-muted)]">{t('report_style_label')}</div>
                  <select
                    value={reportStyle}
                    onChange={(e) => setReportStyle(e.target.value)}
                    className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                    aria-label={t('report_style_aria')}
                  >
                    <option value="apa7">APA 7</option>
                    <option value="gost">{t('report_style_gost')}</option>
                    <option value="simple">{t('report_style_simple')}</option>
                    <option value="editorial">{t('report_style_editorial')}</option>
                    <option value="brutal">{t('report_style_brutal')}</option>
                  </select>
                  <select
                    value={reportDensity}
                    onChange={(e) => setReportDensity(e.target.value)}
                    className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                    aria-label={t('report_density_aria')}
                  >
                    <option value="compact">{t('report_density_compact')}</option>
                    <option value="comfortable">{t('report_density_comfortable')}</option>
                    <option value="spacious">{t('report_density_spacious')}</option>
                  </select>
                  <select
                    value={reportAccent}
                    onChange={(e) => setReportAccent(e.target.value)}
                    className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                    aria-label={t('report_accent_aria')}
                  >
                    <option value="">{t('report_accent_auto')}</option>
                    <option value="#111111">{t('report_accent_black')}</option>
                    <option value="#3498db">{t('report_accent_blue')}</option>
                    <option value="#ff2d55">{t('report_accent_fuchsia')}</option>
                    <option value="#a3ff12">{t('report_accent_lime')}</option>
                  </select>
                </div>

                {aiText && (
                  <MotionDiv 
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.3 }}
                    className="bg-[color:var(--white)] text-[color:var(--text-primary)] p-10 rounded-[2px] relative border border-[color:var(--accent)] overflow-hidden"
                  >
                    <h4 className="font-black text-lg mb-4 flex items-center gap-3">
                      <span className="w-2 h-2 bg-[color:var(--accent)] rounded-[2px]"></span>
                      <span>{t('clinical_interpretation_title')}</span>
                      {aiSource ? (
                        <span className="ml-auto inline-flex items-center rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-2 py-0.5 text-[10px] font-black tracking-widest text-[color:var(--text-secondary)]">
                          {String(aiSource).toUpperCase()}
                        </span>
                      ) : null}
                    </h4>
                    <div className="mt-3 border-l-2 border-[color:var(--accent)] pl-5 py-3 bg-[color:var(--bg-secondary)]">
                      <div className="text-[15px] leading-7 whitespace-pre-line text-[color:var(--text-primary)]">
                        {String(aiText)}
                      </div>
                    </div>
                    <AIProvenanceDetails meta={aiMeta} />
                  </MotionDiv>
                )}

                <button onClick={reset} className="w-full py-4 text-[color:var(--text-secondary)] hover:text-[color:var(--accent)] font-bold text-sm transition-colors mt-8">
                  {t('reset_results')}
                </button>

                <AnimatePresence>
                  {resultsSections.chart && drilldownResult && (
                    <MotionDiv 
                      ref={chartRef} 
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 20 }}
                      className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden"
                    >
                      <div className="px-6 py-5 border-b border-[color:var(--border-color)]">
                        <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{t('plot')}</div>
                        <div className="mt-2 text-sm text-[color:var(--text-secondary)]">{t('plot_selected_metric_desc')}</div>
                      </div>
                      <div className="p-6">
                        <Suspense fallback={chartFallback}>
                          {AnalyticsChartProp ? <AnalyticsChartProp result={drilldownResult} /> : null}
                        </Suspense>
                      </div>
                    </MotionDiv>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>
        </MotionDiv>
      </AnimatePresence>
  );
}
