import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import PromptBuilder from './PromptBuilder';

describe('PromptBuilder model options', () => {
  it('includes requested RouterAI alternatives', () => {
    render(<PromptBuilder />);
    expect(screen.getByText('minimax/minimax-m2.5')).toBeInTheDocument();
    expect(screen.getByText('z-ai/glm-5')).toBeInTheDocument();
    expect(screen.getByText('qwen/qwen3.5-397b-a17b')).toBeInTheDocument();
  });
});
