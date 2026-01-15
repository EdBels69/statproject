import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { I18nextProvider } from 'react-i18next';
import i18n from '../../lib/i18n';
import Settings from './Settings';
import { LanguageProvider } from '../../contexts/LanguageContext';

describe('Settings', () => {
  beforeEach(async () => {
    localStorage.clear();
    localStorage.setItem('preferredLanguage', 'en');
    await i18n.changeLanguage('en');
  });

  it('persists alpha to localStorage', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <LanguageProvider>
          <Settings />
        </LanguageProvider>
      </I18nextProvider>
    );

    expect(screen.getByText('0.05 (Standard)')).toBeInTheDocument();
    fireEvent.click(screen.getByText('0.10 (More Lenient)'));

    expect(localStorage.getItem('statwizard_alpha')).toBe('0.1');
    expect(screen.getByRole('alert')).toHaveTextContent('Settings saved successfully');
  });
});
