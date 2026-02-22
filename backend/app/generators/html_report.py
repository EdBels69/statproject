"""
HTML Report Generator with AI interpretations.
Creates an interactive, printable HTML report.
"""
from typing import Dict, Any, Optional, List
from pathlib import Path
from io import BytesIO
import html
import json
import asyncio

from .base import AbstractGenerator
from app.configs import StudyConfig
from app.llm import interpret_table, interpret_figure, interpret_general_summary


class HTMLReportGenerator(AbstractGenerator):
    """
    Generates interactive HTML report with AI interpretations.
    """

    def __init__(self, study_config: StudyConfig, results: Dict[str, Any]):
        super().__init__(study_config, results)

    def generate(self, output_path: str) -> str:
        """Generate HTML report file."""
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        html_content = self.generate_html()
        out_path.write_text(html_content, encoding="utf-8")
        return str(out_path.resolve())

    def generate_html(self) -> str:
        """Generate HTML content as string."""
        data = self._prepare_data()
        enriched = self._run_coroutine(self._enrich_with_ai(data))
        return self._render_html(enriched)

    def _prepare_data(self) -> Dict[str, Any]:
        """Prepare data for HTML rendering."""
        return {
            "title": self.study_config.title or "Статистический отчёт",
            "objective": self.study_config.objective,
            "study_type": self.study_config.study_type,
            "results": self.results,
            "alpha": self.study_config.alpha,
        }

    async def _enrich_with_ai(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add AI interpretations to results."""
        results = data.get("results", {})
        if not isinstance(results, dict):
            return data

        context = {
            "title": data.get("title"),
            "objective": data.get("objective"),
            "study_type": data.get("study_type"),
            "alpha": data.get("alpha"),
        }

        tasks = []
        task_meta = []

        # Collect tables and figures for AI interpretation
        for step_id, res in results.items():
            if not isinstance(res, dict):
                continue

            # Tables
            if res.get("type") == "table_1" and not res.get("ai_interpretation"):
                table_data = res.get("data") or res.get("table")
                if table_data:
                    tasks.append(interpret_table(
                        title=f"Таблица: {step_id}",
                        table=table_data,
                        context=context
                    ))
                    task_meta.append((step_id, "table"))

            # Figures
            has_plot = any(k in res for k in ["plot_data", "plot_stats", "figure_meta"])
            if has_plot and not res.get("ai_figure_interpretation"):
                figure_meta = {
                    "step_id": step_id,
                    "type": res.get("type"),
                    "plot_data": res.get("plot_data"),
                    "plot_stats": res.get("plot_stats"),
                }
                tasks.append(interpret_figure(
                    title=f"Рисунок: {step_id}",
                    figure_meta=figure_meta,
                    context=context
                ))
                task_meta.append((step_id, "figure"))

        # General summary
        hypotheses = self._build_hypotheses_payload()
        tasks.append(interpret_general_summary(results=results, hypotheses=hypotheses))
        task_meta.append(("__general__", "summary"))

        if not tasks:
            return data

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        next_results = dict(results)
        general_summary = None

        for (step_id, kind), resp in zip(task_meta, responses):
            if isinstance(resp, Exception) or not resp:
                continue

            if kind == "summary":
                general_summary = resp
            elif step_id in next_results:
                res = dict(next_results[step_id])
                if kind == "table":
                    res["ai_interpretation"] = resp
                elif kind == "figure":
                    res["ai_figure_interpretation"] = resp
                next_results[step_id] = res

        return {
            **data,
            "results": next_results,
            "general_summary": general_summary,
        }

    def _build_hypotheses_payload(self) -> Dict[str, Any]:
        """Build hypotheses for AI summary."""
        items = []
        for h in self.study_config.hypotheses:
            items.append({
                "h0": h.h0,
                "h1": h.h1,
                "primary": bool(h.primary),
                "rationale": h.rationale,
            })
        return {"hypotheses": items}

    def _render_html(self, data: Dict[str, Any]) -> str:
        """Render HTML from data."""
        title = html.escape(data.get("title", "Отчёт"))
        objective = html.escape(data.get("objective") or "")
        study_type = html.escape(data.get("study_type") or "")
        alpha = data.get("alpha", 0.05)
        results = data.get("results", {})
        general_summary = data.get("general_summary", "")

        # Build results HTML
        results_html = []
        for step_id, res in results.items():
            if not isinstance(res, dict):
                continue

            step_html = f'<div class="result-block" id="result-{html.escape(step_id)}">'
            step_html += f'<h3>{html.escape(step_id)}</h3>'

            # Method info
            method = res.get("method") or res.get("type") or ""
            if method:
                step_html += f'<div class="method">{html.escape(str(method))}</div>'

            # P-value
            p_val = res.get("p_value")
            if p_val is not None:
                sig_class = "significant" if p_val < alpha else "not-significant"
                step_html += f'<div class="p-value {sig_class}">p = {p_val:.4f}</div>'

            # AI interpretation
            ai_text = res.get("ai_interpretation") or res.get("ai_figure_interpretation")
            if ai_text:
                step_html += f'<div class="ai-interpretation">{html.escape(str(ai_text))}</div>'

            step_html += '</div>'
            results_html.append(step_html)

        results_section = "\n".join(results_html) if results_html else "<p>Нет результатов</p>"

        # General summary section
        summary_section = ""
        if general_summary:
            summary_section = f'''
            <section class="summary">
                <h2>Общий вывод</h2>
                <div class="summary-text">{html.escape(str(general_summary))}</div>
            </section>
            '''

        return f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --primary: #1a1a1a;
            --accent: #e55a00;
            --bg: #fafafa;
            --card-bg: #ffffff;
            --border: #e5e5e5;
            --text: #333333;
            --text-muted: #666666;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        header {{
            border-bottom: 2px solid var(--primary);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}
        h1 {{ font-size: 2rem; font-weight: 800; margin-bottom: 0.5rem; }}
        .meta {{ color: var(--text-muted); font-size: 0.9rem; }}
        section {{ margin-bottom: 2rem; }}
        h2 {{
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }}
        .result-block {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        }}
        .result-block h3 {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }}
        .method {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }}
        .p-value {{
            font-family: monospace;
            font-size: 0.9rem;
            padding: 0.25rem 0.5rem;
            border-radius: 2px;
            display: inline-block;
            margin-bottom: 0.75rem;
        }}
        .significant {{ background: #dcfce7; color: #166534; }}
        .not-significant {{ background: #fef2f2; color: #991b1b; }}
        .ai-interpretation {{
            background: #fffbeb;
            border-left: 3px solid var(--accent);
            padding: 0.75rem 1rem;
            font-size: 0.9rem;
            margin-top: 0.75rem;
        }}
        .summary {{
            background: var(--card-bg);
            border: 2px solid var(--primary);
            border-radius: 4px;
            padding: 1.5rem;
        }}
        .summary-text {{ font-size: 1rem; }}
        @media print {{
            body {{ padding: 1rem; }}
            .result-block {{ break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{title}</h1>
            <div class="meta">
                {f'<span>Цель: {objective}</span>' if objective else ''}
                {f' · <span>Тип: {study_type}</span>' if study_type else ''}
                · <span>α = {alpha}</span>
            </div>
        </header>

        <section class="results">
            <h2>Результаты анализа</h2>
            {results_section}
        </section>

        {summary_section}

        <footer style="margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border); font-size: 0.8rem; color: var(--text-muted);">
            Сгенерировано Clinimetria · {self._get_timestamp()}
        </footer>
    </div>
</body>
</html>'''

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    def _run_coroutine(self, coro):
        """Run async coroutine in sync context."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        return asyncio.run(coro)
