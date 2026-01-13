import React, { useMemo, useCallback } from 'react';
import { VariableSizeList as List } from 'react-window';
import AutoSizer from 'react-virtualized-auto-sizer';
import './VirtualizedResults.css';

/**
 * Virtualized Results Component
 * Optimized for large statistical results on MacBook M1 8GB
 * Uses react-window for efficient rendering of large lists
 */

const VirtualizedResults = ({ 
  results, 
  onResultClick,
  estimatedRowHeight = 60,
  maxVisibleRows = 20
}) => {
  // Memoize row data for performance
  const rowData = useMemo(() => 
    Array.isArray(results) ? results : [],
    [results]
  );

  // Dynamic row height calculation
  const getRowHeight = useCallback((index) => {
    const item = rowData[index];
    if (!item) return estimatedRowHeight;

    // Calculate height based on content complexity
    let height = estimatedRowHeight;
    
    // Adjust for complex objects
    if (item.description && item.description.length > 100) {
      height += Math.floor(item.description.length / 50) * 20;
    }
    
    if (item.metadata && item.metadata.parameters) {
      height += Object.keys(item.metadata.parameters).length * 15;
    }
    
    return Math.min(height, 300); // Cap at 300px
  }, [rowData, estimatedRowHeight]);

  // Row renderer with optimized rendering
  const Row = useCallback(({ index, style }) => {
    const item = rowData[index];
    if (!item) return null;

    return (
      <div 
        style={style}
        className="virtualized-row"
        onClick={() => onResultClick && onResultClick(item)}
        onKeyPress={(e) => e.key === 'Enter' && onResultClick && onResultClick(item)}
        tabIndex={0}
        role="button"
        aria-label={`Result ${index + 1}`}
      >
        <div className="result-content">
          <div className="result-header">
            <h4 className="result-title">
              {item.method || item.test_type || 'Analysis Result'}
            </h4>
            {item.p_value !== undefined && (
              <span className={`p-value ${item.p_value < 0.05 ? 'significant' : ''}`}>
                p = {item.p_value.toFixed(4)}
              </span>
            )}
          </div>
          
          {item.description && (
            <p className="result-description">
              {item.description.length > 150 
                ? `${item.description.substring(0, 150)}...` 
                : item.description
              }
            </p>
          )}
          
          {item.statistic !== undefined && (
            <div className="result-stats">
              <span className="statistic">
                Statistic: {typeof item.statistic === 'number' ? item.statistic.toFixed(3) : item.statistic}
              </span>
              {item.effect_size && (
                <span className="effect-size">
                  Effect: {typeof item.effect_size === 'number' ? item.effect_size.toFixed(3) : item.effect_size}
                </span>
              )}
            </div>
          )}
          
          {item.metadata && (
            <div className="result-metadata">
              <small>
                {item.metadata.timestamp && `Generated: ${new Date(item.metadata.timestamp).toLocaleTimeString()}`}
                {item.metadata.sample_size && ` | N: ${item.metadata.sample_size}`}
              </small>
            </div>
          )}
        </div>
      </div>
    );
  }, [rowData, onResultClick]);

  // Loading state
  if (!rowData.length) {
    return (
      <div className="virtualized-empty">
        <p>No results to display</p>
      </div>
    );
  }

  return (
    <div className="virtualized-container" style={{ height: '100%', minHeight: '400px' }}>
      <AutoSizer>
        {({ height, width }) => (
          <List
            height={height}
            width={width}
            itemCount={rowData.length}
            itemSize={getRowHeight}
            estimatedItemSize={estimatedRowHeight}
            overscanCount={5} // Render 5 extra items for smooth scrolling
            className="virtualized-list"
          >
            {Row}
          </List>
        )}
      </AutoSizer>
      
      {/* Results counter */}
      <div className="virtualized-footer">
        <small>
          Showing {rowData.length} result{rowData.length !== 1 ? 's' : ''} 
          {rowData.length > maxVisibleRows && ` (virtualized)`}
        </small>
      </div>
    </div>
  );
};

// Optimized comparison to prevent unnecessary re-renders
const areEqual = (prevProps, nextProps) => {
  return (
    prevProps.results === nextProps.results &&
    prevProps.estimatedRowHeight === nextProps.estimatedRowHeight &&
    prevProps.onResultClick === nextProps.onResultClick
  );
};

export default React.memo(VirtualizedResults, areEqual);