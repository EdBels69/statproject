import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import PromptBuilder from './PromptBuilder';

describe('PromptBuilder', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    localStorage.clear();
  });

  it('loads COVID preset and renders structured prompt text', () => {
    render(<PromptBuilder />);

    fireEvent.click(screen.getByText('Заполнить COVID-шаблоном'));

    const promptArea = screen.getByLabelText('Сгенерированный промпт');
    expect(promptArea.value).toContain('Оценить связь гликемии с летальным исходом');
    expect(promptArea.value).toContain('=== MULTIVARIABLE MODELS ===');
    expect(promptArea.value).toContain('Глюкоза при поступлении');
  });

  it('updates prompt when research goal changes', () => {
    render(<PromptBuilder />);

    const goalInput = screen.getByLabelText('Цель исследования');
    fireEvent.change(goalInput, { target: { value: 'Проверить связь маркера X с исходом Y' } });

    const promptArea = screen.getByLabelText('Сгенерированный промпт');
    expect(promptArea.value).toContain('Проверить связь маркера X с исходом Y');
  });
});
