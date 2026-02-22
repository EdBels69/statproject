const SIZE_PRESETS = {
  journal: { id: 'journal', label: 'Journal Figure (3.5" × 3")', widthIn: 3.5, heightIn: 3 },
  half: { id: 'half', label: 'Half Page (7" × 5")', widthIn: 7, heightIn: 5 },
  full: { id: 'full', label: 'Full Page (7" × 10")', widthIn: 7, heightIn: 10 },
  poster: { id: 'poster', label: 'Poster (12" × 10")', widthIn: 12, heightIn: 10 },
  custom: { id: 'custom', label: 'Custom', widthIn: 7, heightIn: 5 }
};

function safeNumber(value, fallback) {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function getSvgFromTarget(target) {
  if (!target) return null;
  if (target instanceof SVGSVGElement) return target;
  return target.querySelector?.('svg') || null;
}

function getSvgDimensions(svg) {
  const attrW = safeNumber(svg.getAttribute('width'), null);
  const attrH = safeNumber(svg.getAttribute('height'), null);

  const clientW = safeNumber(svg.clientWidth, null);
  const clientH = safeNumber(svg.clientHeight, null);

  const w = attrW || clientW || 800;
  const h = attrH || clientH || 600;

  return { width: w, height: h };
}

function ensureViewBox(svg, width, height) {
  const vb = svg.getAttribute('viewBox');
  if (vb && vb.trim()) return vb;
  const next = `0 0 ${width} ${height}`;
  svg.setAttribute('viewBox', next);
  return next;
}

function stripGridForPublication(svg) {
  const nodes = Array.from(svg.querySelectorAll('[class]'));
  nodes.forEach((node) => {
    const cls = String(node.getAttribute('class') || '');
    if (cls.includes('recharts-cartesian-grid')) node.remove();
  });
}

function buildSvgString({
  svg,
  widthPx,
  heightPx,
  fontSizePt,
  background,
  title,
  style,
  colors
}) {
  const cloned = svg.cloneNode(true);
  const { width: srcW, height: srcH } = getSvgDimensions(svg);
  ensureViewBox(cloned, srcW, srcH);

  cloned.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  cloned.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');

  if (style === 'publication') stripGridForPublication(cloned);

  const fontSizePx = Math.max(1, Math.round((safeNumber(fontSizePt, 10) / 72) * 96));
  cloned.style.fontSize = `${fontSizePx}px`;
  cloned.style.fontFamily = 'ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif';

  const titleText = String(title || '').trim();
  const hasTitle = Boolean(titleText);
  const titlePad = hasTitle ? Math.round(fontSizePx * 2.6) : 0;

  const inner = cloned.innerHTML;
  const totalHeight = heightPx + titlePad;

  const bgFill = colors?.background || 'transparent';
  const titleFill = colors?.title || 'currentColor';

  const bg = background === 'white'
    ? `<rect x="0" y="0" width="100%" height="100%" fill="${escapeXml(bgFill)}" />`
    : '';

  const titleSvg = hasTitle
    ? `<text x="50%" y="${Math.round(fontSizePx * 1.6)}" text-anchor="middle" font-weight="700" fill="${escapeXml(titleFill)}">${escapeXml(titleText)}</text>`
    : '';

  const wrapped = `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${widthPx}" height="${totalHeight}" viewBox="0 0 ${widthPx} ${totalHeight}">` +
    bg +
    titleSvg +
    `<g transform="translate(0,${titlePad})">` +
    `<svg x="0" y="0" width="${widthPx}" height="${heightPx}" viewBox="${cloned.getAttribute('viewBox')}">` +
    inner +
    `</svg>` +
    `</g>` +
    `</svg>`;

  return { svgString: wrapped, titlePad };
}

function escapeXml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function svgToPngBlob(svgString, widthPx, heightPx, background) {
  const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);

  try {
    const img = await new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('Не удалось загрузить SVG для экспорта'));
      image.src = url;
    });

    const canvas = document.createElement('canvas');
    canvas.width = widthPx;
    canvas.height = heightPx;

    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Не удалось создать canvas');

    if (background === 'white') {
      const root = getComputedStyle(document.documentElement);
      const bgFill = root.getPropertyValue('--white').trim();
      ctx.fillStyle = bgFill;
      ctx.fillRect(0, 0, widthPx, heightPx);
    }

    ctx.drawImage(img, 0, 0, widthPx, heightPx);

    const png = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
    if (!png) throw new Error('Не удалось сформировать PNG');
    return png;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function getExportSizePresets() {
  return Object.values(SIZE_PRESETS);
}

export function resolveExportSize(presetId, widthIn, heightIn) {
  const preset = SIZE_PRESETS[presetId] || SIZE_PRESETS.custom;
  if (preset.id !== 'custom') return { widthIn: preset.widthIn, heightIn: preset.heightIn };
  return {
    widthIn: Math.max(1, safeNumber(widthIn, preset.widthIn)),
    heightIn: Math.max(1, safeNumber(heightIn, preset.heightIn))
  };
}

export async function exportPlot(target, settings, options = {}) {
  const svg = getSvgFromTarget(target);
  if (!svg) throw new Error('SVG не найден для экспорта');

  const format = settings?.format === 'svg' ? 'svg' : 'png';
  const dpi = safeNumber(settings?.dpi, 300);
  const fontSizePt = safeNumber(settings?.fontSizePt, 10);
  const background = settings?.background === 'transparent' ? 'transparent' : 'white';
  const style = settings?.style === 'publication' ? 'publication' : 'web';

  const { widthIn, heightIn } = resolveExportSize(settings?.sizePresetId, settings?.widthIn, settings?.heightIn);
  const pxPerIn = format === 'png' ? dpi : 96;
  const widthPx = Math.round(widthIn * pxPerIn);
  const heightPx = Math.round(heightIn * pxPerIn);

  const title = String(settings?.title ?? options?.defaultTitle ?? '').trim();
  const baseName = String(options?.fileBaseName || 'plot').trim() || 'plot';

  const root = getComputedStyle(document.documentElement);
  const colors = {
    background: root.getPropertyValue('--white').trim(),
    title: root.getPropertyValue('--text-primary').trim()
  };

  const { svgString } = buildSvgString({
    svg,
    widthPx,
    heightPx,
    fontSizePt,
    background,
    title,
    style,
    colors
  });

  if (format === 'svg') {
    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    downloadBlob(blob, `${baseName}.svg`);
    return;
  }

  const totalHeightPx = title ? heightPx + Math.round(((fontSizePt / 72) * dpi) * 2.6) : heightPx;
  const pngBlob = await svgToPngBlob(svgString, widthPx, totalHeightPx, background);
  downloadBlob(pngBlob, `${baseName}_${dpi}dpi.png`);
}
