import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import Settings from './Settings';

describe('Settings', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('persists alpha to localStorage', () => {
    render(<Settings />);

    expect(screen.getByText('0.05 (Standard)')).toBeInTheDocument();
    fireEvent.click(screen.getByText('0.10 (More Lenient)'));

    expect(localStorage.getItem('statwizard_alpha')).toBe('0.1');
    expect(screen.getByRole('alert')).toHaveTextContent('Settings saved successfully');
  });
});

