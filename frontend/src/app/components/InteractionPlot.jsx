import React, { useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';

import { useTranslation } from '../../hooks/useTranslation';
import ExportSettingsModal from './ExportSettingsModal';
import { exportPlot } from '../utils/exportPlot';
import { ArrowDownTrayIcon } from '@heroicons/react/24/outline';

const InteractionPlot = ({ 
  data, 
  width = 600, 
  height = 400, 
  margin = { top: 40, right: 40, bottom: 60, left: 60 } 
}) => {
  const svgRef = useRef();
  const [isExportOpen, setIsExportOpen] = useState(false);
  const { t, currentLanguage } = useTranslation();

  useEffect(() => {
    if (!data || !data.estimated_means) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const estimatedMeans = data.estimated_means;
    const groups = Object.keys(estimatedMeans);
    const timePoints = Object.keys(estimatedMeans[groups[0]] || {});

    if (groups.length === 0 || timePoints.length === 0) return;

    // Prepare data for plotting
    const plotData = [];
    groups.forEach(group => {
      timePoints.forEach(timePoint => {
        const meanData = estimatedMeans[group][timePoint];
        if (meanData) {
          plotData.push({
            group,
            time: parseFloat(timePoint),
            mean: meanData.estimate,
            ci_lower: meanData.ci_lower,
            ci_upper: meanData.ci_upper
          });
        }
      });
    });

    // Create scales
    const xScale = d3.scaleLinear()
      .domain(d3.extent(plotData, d => d.time))
      .range([0, innerWidth])
      .nice();

    const yScale = d3.scaleLinear()
      .domain([
        d3.min(plotData, d => d.ci_lower || d.mean) * 0.95,
        d3.max(plotData, d => d.ci_upper || d.mean) * 1.05
      ])
      .range([innerHeight, 0])
      .nice();

    const root = getComputedStyle(document.documentElement);
    const cssAccent = root.getPropertyValue('--accent').trim() || root.getPropertyValue('--orange').trim();
    const cssText = root.getPropertyValue('--text-primary').trim() || root.getPropertyValue('--black').trim();
    const cssTextSecondary = root.getPropertyValue('--text-secondary').trim() || root.getPropertyValue('--gray-600').trim();
    const cssWhite = root.getPropertyValue('--white').trim();

    // Color scale for groups
    const colorScale = d3.scaleOrdinal()
      .domain(groups)
      .range(groups.map((_, i) => [cssAccent, cssText, cssTextSecondary][i % 3]));

    // Create main group
    const g = svg.append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Add X axis
    const xAxis = d3.axisBottom(xScale)
      .tickFormat(d => `${t('timepoint_prefix')}${d}`);

    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(xAxis)
      .append("text")
      .attr("x", innerWidth / 2)
      .attr("y", 40)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(t('time'));

    // Add Y axis
    const yAxis = d3.axisLeft(yScale);

    g.append("g")
      .call(yAxis)
      .append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", -40)
      .attr("x", -innerHeight / 2)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .text(t('estimated_mean'));

    // Draw confidence intervals
    groups.forEach(group => {
      const groupData = plotData.filter(d => d.group === group);
      
      // Confidence area
      const area = d3.area()
        .x(d => xScale(d.time))
        .y0(d => yScale(d.ci_lower))
        .y1(d => yScale(d.ci_upper))
        .curve(d3.curveMonotoneX);

      g.append("path")
        .datum(groupData)
        .attr("fill", colorScale(group))
        .attr("fill-opacity", 0.2)
        .attr("stroke", "none")
        .attr("d", area);
    });

    // Draw mean lines
    groups.forEach(group => {
      const groupData = plotData.filter(d => d.group === group);
      
      const line = d3.line()
        .x(d => xScale(d.time))
        .y(d => yScale(d.mean))
        .curve(d3.curveMonotoneX);

      g.append("path")
        .datum(groupData)
        .attr("fill", "none")
        .attr("stroke", colorScale(group))
        .attr("stroke-width", 2)
        .attr("d", line);
    });

    // Draw points with error bars
    groups.forEach(group => {
      const groupData = plotData.filter(d => d.group === group);
      
      // Points
      g.selectAll(`.point-${group}`)
        .data(groupData)
        .enter().append("circle")
        .attr("class", `point-${group}`)
        .attr("cx", d => xScale(d.time))
        .attr("cy", d => yScale(d.mean))
        .attr("r", 4)
        .attr("fill", colorScale(group))
        .attr("stroke", cssWhite)
        .attr("stroke-width", 1);

      // Error bars
      groupData.forEach(d => {
        if (d.ci_lower && d.ci_upper) {
          g.append("line")
            .attr("x1", xScale(d.time))
            .attr("x2", xScale(d.time))
            .attr("y1", yScale(d.ci_lower))
            .attr("y2", yScale(d.ci_upper))
            .attr("stroke", colorScale(group))
            .attr("stroke-width", 1);

          // Error bar caps
          g.append("line")
            .attr("x1", xScale(d.time) - 4)
            .attr("x2", xScale(d.time) + 4)
            .attr("y1", yScale(d.ci_lower))
            .attr("y2", yScale(d.ci_lower))
            .attr("stroke", colorScale(group))
            .attr("stroke-width", 1);

          g.append("line")
            .attr("x1", xScale(d.time) - 4)
            .attr("x2", xScale(d.time) + 4)
            .attr("y1", yScale(d.ci_upper))
            .attr("y2", yScale(d.ci_upper))
            .attr("stroke", colorScale(group))
            .attr("stroke-width", 1);
        }
      });
    });

    // Add legend
    const legend = g.append("g")
      .attr("transform", `translate(${innerWidth - 100}, 20)`);

    groups.forEach((group, i) => {
      const legendItem = legend.append("g")
        .attr("transform", `translate(0, ${i * 20})`);

      legendItem.append("line")
        .attr("x1", 0)
        .attr("x2", 20)
        .attr("y1", 10)
        .attr("y2", 10)
        .attr("stroke", colorScale(group))
        .attr("stroke-width", 2);

      legendItem.append("circle")
        .attr("cx", 10)
        .attr("cy", 10)
        .attr("r", 4)
        .attr("fill", colorScale(group))
        .attr("stroke", cssWhite)
        .attr("stroke-width", 1);

      legendItem.append("text")
        .attr("x", 30)
        .attr("y", 10)
        .attr("dy", "0.35em")
        .style("font-size", "12px")
        .text(group);
    });

    // Add title
    svg.append("text")
      .attr("x", width / 2)
      .attr("y", 20)
      .attr("text-anchor", "middle")
      .style("font-size", "14px")
      .style("font-weight", "bold")
      .text(t('time_group_interaction_title'));

    // Add significance annotation if available
    const pValue = typeof data.interaction_p_value === 'number'
      ? data.interaction_p_value
      : (typeof data.interaction?.min_p_value === 'number' ? data.interaction.min_p_value : null);

    if (typeof pValue === 'number') {
      let significance = "";
      
      if (pValue < 0.001) significance = "***";
      else if (pValue < 0.01) significance = "**";
      else if (pValue < 0.05) significance = "*";
      else significance = t('not_significant_short');

      g.append("text")
        .attr("x", innerWidth / 2)
        .attr("y", -10)
        .attr("text-anchor", "middle")
        .style("font-size", "12px")
        .style("font-style", "italic")
        .text(t('interaction_p_value', { p: pValue.toFixed(4), sig: significance }));
    }

  }, [data, width, height, margin, currentLanguage, t]);

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)]">
        <div className="text-[color:var(--text-muted)] text-center">
          <div className="text-2xl mb-2">📈</div>
          <p>{t('upload_data_for_interaction_plot')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="interaction-plot relative">
      <button
        type="button"
        onClick={() => setIsExportOpen(true)}
        className="absolute right-2 top-2 z-10 inline-flex items-center gap-2 px-3 py-2 rounded-[2px] text-xs font-semibold bg-[color:var(--white)] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
      >
        <ArrowDownTrayIcon className="w-4 h-4" />
        Экспорт
      </button>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)]"
      />

      <ExportSettingsModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        defaultTitle={t('time_group_interaction_title')}
        onConfirm={async (settings) => {
          setIsExportOpen(false);
          try {
            await exportPlot(svgRef.current, settings, { fileBaseName: 'interaction_plot', defaultTitle: settings?.title || t('time_group_interaction_title') });
          } catch (e) {
            window.alert(e?.message || 'Не удалось экспортировать график');
          }
        }}
      />
      
      {/* Model statistics */}
      {data.model_statistics && (
        <div className="mt-4 p-4 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)]">
          <h4 className="font-semibold mb-2">{t('model_statistics')}:</h4>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-[color:var(--text-muted)]">{t('aic')}: </span>
              <span className="font-medium">{data.model_statistics.aic?.toFixed(1)}</span>
            </div>
            <div>
              <span className="text-[color:var(--text-muted)]">{t('bic')}: </span>
              <span className="font-medium">{data.model_statistics.bic?.toFixed(1)}</span>
            </div>
            <div>
              <span className="text-[color:var(--text-muted)]">{t('marginal_r2')}: </span>
              <span className="font-medium">{data.model_statistics.marginal_r2?.toFixed(3)}</span>
            </div>
            <div>
              <span className="text-[color:var(--text-muted)]">{t('conditional_r2')}: </span>
              <span className="font-medium">{data.model_statistics.conditional_r2?.toFixed(3)}</span>
            </div>
          </div>
          
          {data.fixed_effects && (
            <div className="mt-3">
              <h5 className="font-medium mb-1">{t('fixed_effects')}:</h5>
              <div className="space-y-1 text-xs">
                {Object.entries(data.fixed_effects).map(([effect, stats]) => (
                  <div key={effect} className="flex justify-between">
                    <span>{effect}:</span>
                    <span>
                      {t('beta')}: {stats.estimate?.toFixed(3)}, {t('p_value')}: {stats.p_value?.toFixed(4)}
                      {stats.p_value < 0.05 && <span className="text-[color:var(--error)] ml-1">*</span>}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default InteractionPlot;
