import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useTranslation } from '../../../hooks/useTranslation';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../ui/Table';
import Button from '../ui/Button';
import { formatP, formatNum, getGroupStatsRows, getPostHocRows, getEffectColor } from './utils';
import { StatTooltip } from '../education';

export default function TimepointBatchAnalysisView({ 
  result, 
  legacyStructure = false,
  runDrilldown,
  multiplicityLabel = 'FDR',
  postHocLabel = 'Tukey',
  postHocCorrectionLabel = 'FDR',
  postHocTerm = 'post_hoc',
  onDownloadReport,
  onDownloadDocx,
  onDownloadHtml,
  inspector: propInspector,
  setInspector: propSetInspector
}) {
  const { t } = useTranslation();
  const [localInspector, setLocalInspector] = useState(null);

  const inspector = propInspector !== undefined ? propInspector : localInspector;
  const setInspector = propSetInspector || setLocalInspector;

  if (!result) return null;

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.03
      }
    }
  };

  const item = {
    hidden: { opacity: 0, x: -10 },
    show: { opacity: 1, x: 0 }
  };
  
  // Legacy structure: result.results object
  if (legacyStructure || (result.results && typeof result.results === 'object' && !result.slices)) {
      return (
        <div className="space-y-4">
          <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
            <div className="px-6 py-5 border-b border-[color:var(--border-color)]">
              <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{result.protocol_name || t('analysis_results')}</div>
              <div className="mt-2 text-sm text-[color:var(--text-secondary)]">{t('timepoints_row_desc')}</div>
            </div>
            <div className="p-6">
              <Table className="w-full text-sm">
                <TableHeader className="text-[color:var(--text-secondary)]">
                  <TableRow className="border-b border-[color:var(--border-color)]">
                    <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_metric')}</TableHead>
                    <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_timepoint')}</TableHead>
                    <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">p</TableHead>
                    <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('stat_short')}</TableHead>
                    <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">{t('header_significant')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(result.results)
                    .sort(([a], [b]) => String(a).localeCompare(String(b)))
                    .flatMap(([targetName, res]) => {
                      if (!res || res.type !== 'longitudinal_comparison' || !res.slices) return [];
                      return Object.entries(res.slices)
                        .sort(([a], [b]) => String(a).localeCompare(String(b)))
                        .map(([slice, sliceRes]) => {
                          const p = sliceRes?.p_value;
                          const stat = sliceRes?.stats ?? sliceRes?.stat_value;
                          const sig = sliceRes?.significant;
                          return (
                            <TableRow key={`${targetName}__${slice}`} className="border-b border-[color:var(--border-color)] last:border-b-0">
                              <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{targetName}</TableCell>
                              <TableCell className="py-3 pr-4 text-[color:var(--text-secondary)]">{slice}</TableCell>
                              <TableCell className="py-3 pr-4 font-mono font-black text-[color:var(--text-primary)]">
                                {typeof p === 'number' ? (p < 0.001 ? '< 0.001' : p.toFixed(4)) : '—'}
                              </TableCell>
                              <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">
                                {typeof stat === 'number' ? stat.toFixed(2) : '—'}
                              </TableCell>
                              <TableCell className="py-3">
                                <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${sig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                  {sig ? t('yes') : t('no')}
                                </span>
                              </TableCell>
                            </TableRow>
                          );
                        });
                    })}
                </TableBody>
              </Table>
            </div>
          </div>
          <div className="flex justify-center gap-3 flex-wrap">
             {onDownloadReport && (
                <Button variant="secondary" onClick={onDownloadReport} className="px-8">
                    <span>📥</span> {t('download_report_pdf')}
                </Button>
             )}
             {onDownloadDocx && (
                <Button variant="ghost" onClick={onDownloadDocx} className="px-8">
                    <span>⌁</span> {t('download_report_docx')}
                </Button>
             )}
             {onDownloadHtml && (
                <Button variant="ghost" onClick={onDownloadHtml} className="px-8">
                    <span>🌐</span> {t('download_report_html')}
                </Button>
             )}
          </div>
        </div>
      );
  }

  // New structure: timepoint_batch_analysis
  if (result.type === 'timepoint_batch_analysis' && result.slices) {
      return (
        <div className="space-y-4">
          <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
            <div className="px-6 py-5 border-b border-[color:var(--border-color)]">
              <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{t('all_quant_timepoints')}</div>
              <div className="mt-2 text-sm text-[color:var(--text-secondary)]">{t('timepoints_table_desc')}</div>
            </div>
            <div className="p-6">
              <Table className="w-full text-sm">
                <TableHeader className="text-[color:var(--text-secondary)]">
                  <TableRow className="border-b border-[color:var(--border-color)]">
                    <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_slice')}</TableHead>
                    <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_metric')}</TableHead>
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
                    <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('stat_short')}</TableHead>
                    <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('header_significant')}</TableHead>
                    <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">{t('header_actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody as={motion.tbody} variants={container} initial="hidden" animate="show">
                  {Object.entries(result.slices)
                    .sort(([a], [b]) => String(a).localeCompare(String(b)))
                    .flatMap(([slice, sliceRes]) => {
                      const items = Array.isArray(sliceRes?.items) ? sliceRes.items : [];
                      return items
                        .slice()
                        .sort((a, b) => String(a?.target || '').localeCompare(String(b?.target || '')))
                        .map((r) => {
                          const p = r?.p_value;
                          const pAdj = r?.p_value_adj;
                          const stat = r?.stat_value;
                          const sig = r?.significant_adj ?? r?.significant;
                          const inspectorKey = `${slice}__${String(r?.target)}`;
                          return (
                            <motion.tr 
                              variants={item}
                              key={inspectorKey} 
                              className="border-b border-[color:var(--border-color)] last:border-b-0"
                            >
                              <TableCell className="py-3 pr-4 text-[color:var(--text-secondary)]">{slice}</TableCell>
                              <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{r?.target}</TableCell>
                              <TableCell className="py-3 pr-4 font-mono font-black text-[color:var(--text-primary)]">{formatP(p)}</TableCell>
                              <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(pAdj)}</TableCell>
                              <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatNum(stat, 2)}</TableCell>
                              <TableCell className={`py-3 pr-4 font-mono font-bold ${getEffectColor(r?.effect_size)}`}>
                                {formatNum(r?.effect_size, 2)}
                                {r?.effect_size_name ? <span className="ml-1 text-[10px] opacity-60 font-normal">{r.effect_size_name}</span> : null}
                              </TableCell>
                              <TableCell className="py-3">
                                <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${sig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                  {sig ? t('yes') : t('no')}
                                </span>
                              </TableCell>
                              <TableCell className="py-3">
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => setInspector((prev) => (prev?.key === inspectorKey ? null : { key: inspectorKey, target: r?.target, slice, item: r }))}
                                    className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                                  >
                                    {t('details')}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => runDrilldown && runDrilldown({ target: r?.target, slice })}
                                    className="px-3 py-2 rounded-[2px] border border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-xs font-black uppercase tracking-widest text-[color:var(--text-primary)] hover:bg-[color:var(--white)] transition-colors"
                                  >
                                    {t('plot')}
                                  </button>
                                </div>
                              </TableCell>
                            </motion.tr>
                          );
                        });
                    })}
                </TableBody>
              </Table>

              {inspector?.item && (
                <div className="mt-8 border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                  <div className="px-6 py-4 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-6">
                    <div>
                      <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{t('details')}</div>
                      <div className="mt-1 font-black text-[color:var(--text-primary)]">
                        {inspector?.slice ? `${inspector.slice} · ` : ''}{inspector?.target}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setInspector(null)}
                      className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                    >
                      {t('close')}
                    </button>
                  </div>
                  <div className="p-6 space-y-8 bg-[color:var(--white)]">
                    <div>
                      <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{t('descriptive_statistics')}</div>
                      {getGroupStatsRows(inspector.item?.plot_stats).length ? (
                        <div className="mt-4 overflow-x-auto">
                          <Table className="w-full text-sm">
                            <TableHeader className="text-[color:var(--text-secondary)]">
                              <TableRow className="border-b border-[color:var(--border-color)]">
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{t('group')}</TableHead>
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">n</TableHead>
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Mean ± SD</TableHead>
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Median [IQR]</TableHead>
                                <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">Min–Max</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {getGroupStatsRows(inspector.item?.plot_stats).map(({ groupName, s }) => (
                                <TableRow key={String(groupName)} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                  <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{groupName}</TableCell>
                                  <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{typeof s?.count === 'number' ? String(s.count) : '—'}</TableCell>
                                  <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.mean, 2)} ± ${formatNum(s?.sd, 2)}`}</TableCell>
                                  <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.median, 2)} [${formatNum(s?.q1, 2)}; ${formatNum(s?.q3, 2)}]`}</TableCell>
                                  <TableCell className="py-3 font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.min, 2)}–${formatNum(s?.max, 2)}`}</TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      ) : (
                        <div className="mt-3 text-sm text-[color:var(--text-secondary)]">{t('no_stats_for_result')}</div>
                      )}
                    </div>

                    <div>
                      <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{t('post_hoc')}</div>
                      <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                        {t('method')}: {' '}
                        <StatTooltip term={postHocTerm} level="junior" position="top">
                          <span className="font-mono font-black text-[color:var(--text-primary)]">{postHocLabel}</span>
                        </StatTooltip>
                        {' '}· {t('correction')}: {' '}
                        <StatTooltip term="post_hoc_correction" level="junior" position="top">
                          <span className="font-mono font-black text-[color:var(--text-primary)]">{postHocCorrectionLabel}</span>
                        </StatTooltip>
                      </div>
                      {getPostHocRows(inspector.item?.post_hoc).length ? (
                        <div className="mt-4 overflow-x-auto">
                          <Table className="w-full text-sm">
                            <TableHeader className="text-[color:var(--text-secondary)]">
                              <TableRow className="border-b border-[color:var(--border-color)]">
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">A</TableHead>
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">B</TableHead>
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                                  {postHocCorrectionLabel === 'none' ? 'p' : `p(${postHocCorrectionLabel})`}
                                </TableHead>
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                                  <StatTooltip term="p_value" level="junior" position="top">
                                    <span>p(raw)</span>
                                  </StatTooltip>
                                </TableHead>
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                                  <StatTooltip term="p_value_adj" level="junior" position="top">
                                    <span>p(adj)</span>
                                  </StatTooltip>
                                </TableHead>
                                <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">{t('header_significant')}</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {getPostHocRows(inspector.item?.post_hoc).map((r, idx) => {
                                const raw = r?.p_value;
                                const adj = r?.p_value_adj;
                                const pShown = typeof adj === 'number' ? adj : raw;
                                const sig = r?.significant_adj ?? r?.significant;
                                return (
                                  <TableRow key={`${String(r?.group1)}__${String(r?.group2)}__${idx}`} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                    <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{String(r?.group1 ?? '')}</TableCell>
                                    <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{String(r?.group2 ?? '')}</TableCell>
                                    <TableCell className="py-3 pr-4 font-mono font-black text-[color:var(--text-primary)]">{formatP(pShown)}</TableCell>
                                    <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(raw)}</TableCell>
                                    <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(adj)}</TableCell>
                                    <TableCell className="py-3">
                                      <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${sig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                        {sig ? t('yes') : t('no')}
                                      </span>
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                            </TableBody>
                          </Table>
                        </div>
                      ) : (
                        <div className="mt-3 text-sm text-[color:var(--text-secondary)]">{t('posthoc_not_required')}</div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="flex justify-center gap-3 flex-wrap">
             {onDownloadReport && (
                <Button variant="secondary" onClick={onDownloadReport} className="px-8">
                    <span>📥</span> {t('download_report_pdf')}
                </Button>
             )}
             {onDownloadDocx && (
                <Button variant="ghost" onClick={onDownloadDocx} className="px-8">
                    <span>⌁</span> {t('download_report_docx')}
                </Button>
             )}
             {onDownloadHtml && (
                <Button variant="ghost" onClick={onDownloadHtml} className="px-8">
                    <span>🌐</span> {t('download_report_html')}
                </Button>
             )}
          </div>
        </div>
      );
  }

  return null;
}
