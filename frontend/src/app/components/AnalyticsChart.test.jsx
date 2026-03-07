import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AnalyticsChart from './AnalyticsChart';

vi.mock('recharts', () => {
  const passthrough = (name) => ({ children }) => <div data-testid={name}>{children}</div>;
  return {
    BarChart: passthrough('BarChart'),
    Bar: passthrough('Bar'),
    XAxis: passthrough('XAxis'),
    YAxis: passthrough('YAxis'),
    CartesianGrid: passthrough('CartesianGrid'),
    Tooltip: passthrough('Tooltip'),
    Legend: passthrough('Legend'),
    ResponsiveContainer: passthrough('ResponsiveContainer'),
    ScatterChart: passthrough('ScatterChart'),
    Scatter: passthrough('Scatter'),
    Line: passthrough('Line'),
    LineChart: passthrough('LineChart'),
    ZAxis: passthrough('ZAxis'),
    ErrorBar: passthrough('ErrorBar'),
    Cell: passthrough('Cell'),
  };
});

describe('AnalyticsChart', () => {
  it('renders bland-altman branch', () => {
    render(
      <AnalyticsChart
        result={{
          method: 'bland_altman',
          plot_data: [
            { x: 10, y: 0.3 },
            { x: 12, y: -0.2 },
          ],
          plot_reference_lines: {
            mean_difference: { y: 0.05 },
            loa_lower: { y: -1.2 },
            loa_upper: { y: 1.3 },
            zero: { y: 0 },
          },
        }}
      />
    );
    expect(screen.getByText('Bland-Altman Agreement Plot')).toBeTruthy();
  });

  it('renders time-series branch', () => {
    render(
      <AnalyticsChart
        result={{
          method: 'time_series_analysis',
          plot_data: [
            { x: '2025-01-01', y: 1.0, trend: 1.1 },
            { x: '2025-01-02', y: 1.4, trend: 1.2 },
            { x: '2025-01-03', y: 1.1, trend: 1.3 },
          ],
          forecast: {
            points: [
              { x: '2025-01-04', y: 1.5 },
              { x: '2025-01-05', y: 1.6 },
            ],
          },
          time_axis_kind: 'datetime',
          time_quality: {
            quality: 'warning',
            datetime_parse_ratio: 1,
            min_year: 1970,
            max_year: 1970,
            inferred_frequency: 'D',
            flags: ['epoch_artifact_risk'],
          },
          warnings: [
            'Calendar years are concentrated in 1970-1985; verify date parsing to avoid Unix-epoch artifacts.',
          ],
        }}
      />
    );
    expect(screen.getByText('Time Series')).toBeTruthy();
    expect(screen.getByText('Time Quality:')).toBeTruthy();
    expect(screen.getByText('High risk')).toBeTruthy();
    expect(screen.getByText('Chronology Warnings')).toBeTruthy();
    expect(screen.getByText('Flags: epoch_artifact_risk')).toBeTruthy();
  });
});
