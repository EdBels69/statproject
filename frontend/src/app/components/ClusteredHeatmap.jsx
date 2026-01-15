import React, { useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';

import { useTranslation } from '../../hooks/useTranslation';
import ExportSettingsModal from './ExportSettingsModal';
import { exportPlot } from '../utils/exportPlot';
import { ArrowDownTrayIcon } from '@heroicons/react/24/outline';

const ClusteredHeatmap = ({ 
  data, 
  width = 600, 
  height = 500, 
  margin = { top: 80, right: 120, bottom: 80, left: 120 } 
}) => {
  const svgRef = useRef();
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [hoveredCell, setHoveredCell] = useState(null);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const { t, currentLanguage } = useTranslation();

  const getCorrelationColor = (value) => {
    if (typeof document === 'undefined') return 'currentColor';
    const root = getComputedStyle(document.documentElement);
    const cssAccent = root.getPropertyValue('--accent').trim();
    const cssError = root.getPropertyValue('--error').trim();
    const cssBgSecondary = root.getPropertyValue('--bg-secondary').trim();
    const interpolator = d3.interpolateRgbBasis([cssError, cssBgSecondary, cssAccent]);
    const clamped = Math.min(1, Math.max(0, (Number(value) + 1) / 2));
    return interpolator(clamped);
  };

  useEffect(() => {
    if (!data || !data.correlation_matrix || !data.dendrogram) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const correlationMatrix = data.correlation_matrix;
    const clusterAssignments = data.cluster_assignments || {};
    const variableOrder = data.variable_order || (Array.isArray(correlationMatrix?.variables) ? correlationMatrix.variables : Object.keys(correlationMatrix));

    const correlationLookup = (() => {
      if (!correlationMatrix) return {};
      if (Array.isArray(correlationMatrix.variables) && Array.isArray(correlationMatrix.values)) {
        const lookup = {};
        correlationMatrix.variables.forEach((rowVar, i) => {
          lookup[rowVar] = {};
          correlationMatrix.variables.forEach((colVar, j) => {
            const v = correlationMatrix.values?.[i]?.[j];
            lookup[rowVar][colVar] = typeof v === 'number' ? v : 0;
          });
        });
        return lookup;
      }
      return correlationMatrix;
    })();

    // Create main group
    const g = svg.append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const root = getComputedStyle(document.documentElement);
    const cssAccent = root.getPropertyValue('--accent').trim();
    const cssError = root.getPropertyValue('--error').trim();
    const cssBgSecondary = root.getPropertyValue('--bg-secondary').trim();
    const cssBorder = root.getPropertyValue('--border-color').trim();
    const cssTextPrimary = root.getPropertyValue('--text-primary').trim();
    const cssTextSecondary = root.getPropertyValue('--text-secondary').trim();
    const cssWhite = root.getPropertyValue('--white').trim();

    const colorScale = d3.scaleDiverging()
      .domain([-1, 0, 1])
      .interpolator(d3.interpolateRgbBasis([cssError, cssBgSecondary, cssAccent]));

    // Create heatmap
    const cellSize = Math.min(innerWidth, innerHeight) / variableOrder.length;

    // Draw heatmap cells
    g.selectAll(".cell")
      .data(variableOrder.flatMap((rowVar, i) => 
        variableOrder.map((colVar, j) => ({
          rowVar,
          colVar,
          value: correlationLookup[rowVar]?.[colVar] || 0,
          x: j * cellSize,
          y: i * cellSize,
          rowCluster: clusterAssignments[rowVar],
          colCluster: clusterAssignments[colVar]
        }))
      ))
      .enter().append("rect")
      .attr("class", "cell")
      .attr("x", d => d.x)
      .attr("y", d => d.y)
      .attr("width", cellSize)
      .attr("height", cellSize)
      .attr("fill", d => colorScale(d.value))
      .attr("stroke", cssWhite)
      .attr("stroke-width", 0.5)
      .style("cursor", "pointer")
      .on("mouseover", function(_event, d) {
        setHoveredCell(d);
        d3.select(this).attr("stroke-width", 2).attr("stroke", cssTextPrimary);
      })
      .on("mouseout", function() {
        setHoveredCell(null);
        d3.select(this).attr("stroke-width", 0.5).attr("stroke", cssWhite);
      })
      .on("click", function(_event, d) {
        // Toggle cluster selection
        if (selectedCluster === d.rowCluster) {
          setSelectedCluster(null);
        } else {
          setSelectedCluster(d.rowCluster);
        }
      });

    // Add cluster borders
    const clusterGroups = {};
    variableOrder.forEach((variable, i) => {
      const cluster = clusterAssignments[variable];
      if (!clusterGroups[cluster]) {
        clusterGroups[cluster] = { start: i, count: 1 };
      } else {
        clusterGroups[cluster].count++;
      }
    });

    Object.entries(clusterGroups).forEach(([cluster, { start, count }]) => {
      g.append("rect")
        .attr("class", "cluster-border")
        .attr("x", start * cellSize - 2)
        .attr("y", start * cellSize - 2)
        .attr("width", count * cellSize + 4)
        .attr("height", count * cellSize + 4)
        .attr("fill", "none")
        .attr("stroke", selectedCluster === cluster ? cssAccent : cssTextSecondary)
        .attr("stroke-width", selectedCluster === cluster ? 3 : 1)
        .attr("stroke-dasharray", selectedCluster === cluster ? "" : "4,4")
        .style("pointer-events", "none");
    });

    // Add variable labels
    g.selectAll(".label")
      .data(variableOrder)
      .enter().append("text")
      .attr("class", "label")
      .attr("text-anchor", "end")
      .attr("dy", ".32em")
      .attr("x", -5)
      .attr("y", (d, i) => i * cellSize + cellSize / 2)
      .text(d => d)
      .style("font-size", "10px")
      .style("fill", cssTextSecondary)
      .style("cursor", "pointer")
      .on("mouseover", function() {
        d3.select(this).style("font-weight", "bold");
      })
      .on("mouseout", function() {
        d3.select(this).style("font-weight", "normal");
      });

    // Add column labels
    g.selectAll(".col-label")
      .data(variableOrder)
      .enter().append("text")
      .attr("class", "col-label")
      .attr("text-anchor", "start")
      .attr("transform", `rotate(-90)`)
      .attr("dy", ".32em")
      .attr("x", (d, i) => i * cellSize + cellSize / 2)
      .attr("y", -5)
      .text(d => d)
      .style("font-size", "10px")
      .style("fill", cssTextSecondary)
      .style("cursor", "pointer");

    // Add color legend
    const legendWidth = 100;
    const legendHeight = 10;
    const legend = svg.append("g")
      .attr("transform", `translate(${margin.left},${margin.top - 40})`);

    const legendScale = d3.scaleLinear()
      .domain([-1, 1])
      .range([0, legendWidth]);

    const legendAxis = d3.axisBottom(legendScale)
      .ticks(5)
      .tickFormat(d3.format(".1f"));

    legend.append("g")
      .attr("transform", `translate(0,${legendHeight})`)
      .call(legendAxis);

    legend.selectAll('path,line')
      .attr('stroke', cssBorder);
    legend.selectAll('text')
      .attr('fill', cssTextSecondary)
      .style('font-size', '10px');

    const defs = svg.append("defs");
    const gradient = defs.append("linearGradient")
      .attr("id", "correlation-gradient")
      .attr("x1", "0%")
      .attr("x2", "100%")
      .attr("y1", "0%")
      .attr("y2", "0%");

    gradient.selectAll("stop")
      .data(colorScale.ticks().map((t, i, n) => ({
        offset: `${100 * i / n.length}%`,
        color: colorScale(t)
      })))
      .enter().append("stop")
      .attr("offset", d => d.offset)
      .attr("stop-color", d => d.color);

    legend.append("rect")
      .attr("width", legendWidth)
      .attr("height", legendHeight)
      .style("fill", "url(#correlation-gradient)")
      .attr("stroke", cssBorder);

    // Add title
    svg.append("text")
      .attr("x", width / 2)
      .attr("y", 20)
      .attr("text-anchor", "middle")
      .style("font-size", "16px")
      .style("font-weight", "bold")
      .style('fill', cssTextPrimary)
      .text(t('clustered_correlation_title'));

    // Add cluster info
    if (data.cluster_info) {
      const clusterInfo = g.append("g")
        .attr("transform", `translate(${innerWidth + 20}, 0)`);

      Object.entries(data.cluster_info).forEach(([cluster, info], i) => {
        clusterInfo.append("rect")
          .attr("x", 0)
          .attr("y", i * 25)
          .attr("width", 15)
          .attr("height", 15)
          .attr("fill", getClusterColor(cluster));

        clusterInfo.append("text")
          .attr("x", 20)
          .attr("y", i * 25 + 12)
          .style("font-size", "12px")
          .style('fill', cssTextSecondary)
          .text(t('cluster_label_variables', { cluster, count: info.variables.length }));
      });
    }

  }, [data, width, height, margin, selectedCluster, currentLanguage, t]);

  const getClusterColor = (cluster) => {
    if (typeof document === 'undefined') return 'currentColor';
    const root = getComputedStyle(document.documentElement);
    const cssAccent = root.getPropertyValue('--accent').trim();
    const c = d3.color(cssAccent);
    if (!c) return cssAccent || 'currentColor';
    const alphas = [1, 0.85, 0.7, 0.55, 0.4, 0.25];
    c.opacity = alphas[Number(cluster) % alphas.length] ?? 1;
    return c.formatRgb();
  };

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)]">
        <div className="text-[color:var(--text-secondary)] text-center">
          <div className="text-2xl mb-2">📊</div>
          <p>{t('upload_data_for_heatmap')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="clustered-heatmap relative">
      {/* Tooltip */}
      {hoveredCell && (
        <div className="absolute bg-[color:var(--white)] border border-[color:var(--border-color)] p-3 rounded-[2px]"
             style={{ 
               left: hoveredCell.x + margin.left + 20, 
               top: hoveredCell.y + margin.top + 20 
             }}>
          <div className="text-sm font-semibold text-[color:var(--text-primary)]">
            {hoveredCell.rowVar} × {hoveredCell.colVar}
          </div>
          <div className="text-lg font-bold" style={{ color: getCorrelationColor(hoveredCell.value) }}>
            {t('corr_r_short', { value: hoveredCell.value.toFixed(3) })}
          </div>
          <div className="text-xs text-[color:var(--text-secondary)]">
            {t('row_cluster')}: {hoveredCell.rowCluster || t('not_available_short')}<br/>
            {t('col_cluster')}: {hoveredCell.colCluster || t('not_available_short')}
          </div>
        </div>
      )}

      {/* Main visualization */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setIsExportOpen(true)}
          className="absolute right-2 top-2 z-10 inline-flex items-center gap-2 px-3 py-2 rounded-[2px] text-xs font-semibold bg-[color:var(--white)] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]"
        >
          <ArrowDownTrayIcon className="w-4 h-4" />
          Экспорт
        </button>
        <svg
          ref={svgRef}
          width={width}
          height={height}
          className="border border-[color:var(--border-color)] rounded-[2px]"
        />
      </div>

      <ExportSettingsModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        defaultTitle={t('clustered_correlation_title')}
        onConfirm={async (settings) => {
          setIsExportOpen(false);
          try {
            await exportPlot(svgRef.current, settings, { fileBaseName: 'clustered_heatmap', defaultTitle: settings?.title || t('clustered_correlation_title') });
          } catch (e) {
            window.alert(e?.message || 'Не удалось экспортировать график');
          }
        }}
      />

      {/* Statistics */}
      {data.statistics && (
        <div className="mt-4 p-4 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)]">
          <h4 className="font-semibold mb-2 text-[color:var(--text-primary)]">{t('clustering_statistics')}</h4>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-[color:var(--text-secondary)]">{t('n_clusters')}: </span>
              <span className="font-medium text-[color:var(--text-primary)]">{data.statistics.n_clusters}</span>
            </div>
            <div>
              <span className="text-[color:var(--text-secondary)]">{t('avg_cluster_size')}: </span>
              <span className="font-medium text-[color:var(--text-primary)]">{data.statistics.avg_cluster_size?.toFixed(1)}</span>
            </div>
            <div>
              <span className="text-[color:var(--text-secondary)]">{t('within_cluster_corr')}: </span>
              <span className="font-medium text-[color:var(--text-primary)]">{data.statistics.within_cluster_corr?.toFixed(3)}</span>
            </div>
            <div>
              <span className="text-[color:var(--text-secondary)]">{t('between_cluster_corr')}: </span>
              <span className="font-medium text-[color:var(--text-primary)]">{data.statistics.between_cluster_corr?.toFixed(3)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClusteredHeatmap;
