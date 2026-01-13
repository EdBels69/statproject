import React, { useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';

const ClusteredHeatmap = ({ 
  data, 
  width = 600, 
  height = 500, 
  margin = { top: 80, right: 120, bottom: 80, left: 120 } 
}) => {
  const svgRef = useRef();
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [hoveredCell, setHoveredCell] = useState(null);

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

    // Color scale for correlations
    const colorScale = d3.scaleDiverging()
      .domain([-1, 0, 1])
      .interpolator(d3.interpolateRdBu);

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
      .attr("stroke", "#fff")
      .attr("stroke-width", 0.5)
      .style("cursor", "pointer")
      .on("mouseover", function(_event, d) {
        setHoveredCell(d);
        d3.select(this).attr("stroke-width", 2).attr("stroke", "#000");
      })
      .on("mouseout", function() {
        setHoveredCell(null);
        d3.select(this).attr("stroke-width", 0.5).attr("stroke", "#fff");
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
        .attr("stroke", selectedCluster === cluster ? "#ff6b35" : "#666")
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
      .attr("stroke", "#ccc");

    // Add title
    svg.append("text")
      .attr("x", width / 2)
      .attr("y", 20)
      .attr("text-anchor", "middle")
      .style("font-size", "16px")
      .style("font-weight", "bold")
      .text("Кластерный анализ корреляций");

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
          .text(`Кластер ${cluster}: ${info.variables.length} переменных`);
      });
    }

  }, [data, width, height, margin, selectedCluster]);

  const getClusterColor = (cluster) => {
    const colors = [
      '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
      '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
    ];
    return colors[cluster % colors.length];
  };

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg">
        <div className="text-gray-500 text-center">
          <div className="text-2xl mb-2">📊</div>
          <p>Загрузите данные для отображения тепловой карты</p>
        </div>
      </div>
    );
  }

  return (
    <div className="clustered-heatmap">
      {/* Tooltip */}
      {hoveredCell && (
        <div className="absolute bg-white border border-gray-300 p-3 rounded shadow-lg"
             style={{ 
               left: hoveredCell.x + margin.left + 20, 
               top: hoveredCell.y + margin.top + 20 
             }}>
          <div className="text-sm font-semibold">
            {hoveredCell.rowVar} × {hoveredCell.colVar}
          </div>
          <div className="text-lg font-bold"
               style={{ color: d3.interpolateRdBu((hoveredCell.value + 1) / 2) }}>
            r = {hoveredCell.value.toFixed(3)}
          </div>
          <div className="text-xs text-gray-600">
            Кластер строк: {hoveredCell.rowCluster || 'Н/Д'}<br/>
            Кластер столбцов: {hoveredCell.colCluster || 'Н/Д'}
          </div>
        </div>
      )}

      {/* Main visualization */}
      <svg
        ref={svgRef}
        width={width}
        height={height}
        className="border border-gray-200 rounded-lg"
      />

      {/* Statistics */}
      {data.statistics && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <h4 className="font-semibold mb-2">Статистика кластеризации:</h4>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Количество кластеров: </span>
              <span className="font-medium">{data.statistics.n_clusters}</span>
            </div>
            <div>
              <span className="text-gray-600">Средний размер кластера: </span>
              <span className="font-medium">{data.statistics.avg_cluster_size?.toFixed(1)}</span>
            </div>
            <div>
              <span className="text-gray-600">Внутрикластерная корреляция: </span>
              <span className="font-medium">{data.statistics.within_cluster_corr?.toFixed(3)}</span>
            </div>
            <div>
              <span className="text-gray-600">Межкластерная корреляция: </span>
              <span className="font-medium">{data.statistics.between_cluster_corr?.toFixed(3)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClusteredHeatmap;
