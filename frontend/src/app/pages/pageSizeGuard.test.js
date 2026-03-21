import { statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const PAGE_SIZE_LIMIT_BYTES = 50 * 1024;

const GUARDED_PAGES = [
  'src/app/pages/Analyze.jsx',
  'src/app/pages/ProtocolSorcerer.jsx',
  'src/app/pages/AnalysisDesignLegacy.jsx',
  'src/app/pages/Profile.jsx',
];

const CURRENT_DIR = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = path.resolve(CURRENT_DIR, '../../..');

describe('page bundle size guard', () => {
  for (const relPath of GUARDED_PAGES) {
    it(`${relPath} stays below 50KB`, () => {
      const absPath = path.resolve(FRONTEND_ROOT, relPath);
      const size = statSync(absPath).size;
      expect(size).toBeLessThanOrEqual(PAGE_SIZE_LIMIT_BYTES);
    });
  }
});
