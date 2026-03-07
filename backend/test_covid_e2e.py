"""
End-to-End Copilot Test: COVID-19 Analysis
"""
import asyncio
import os
import sys
import json

sys.path.append(os.getcwd())

from app.copilot.engine import CopilotEngine

async def main():
    engine = CopilotEngine()
    
    dataset_path = os.path.abspath("workspace/covid19_dataset.csv")
    
    # Expert prompt (acting as user)
    user_request = """
    Проведите комплексный статистический анализ госпитализированных пациентов с COVID-19:
    
    1. БАЗОВАЯ ХАРАКТЕРИСТИКА:
       - Демография (возраст, пол)
       - Длительность госпитализации
       - Исходы (выписан/умер)
    
    2. КЛИНИЧЕСКИЕ ПОКАЗАТЕЛИ ПРИ ПОСТУПЛЕНИИ:
       - Витальные параметры (АД, ЧДД, SpO2, температура)
       - Тяжесть состояния (qSOFA, FiO2)
       - Лабораторные маркеры воспаления (WBC, LYM%, фибриноген)
    
    3. СРАВНИТЕЛЬНЫЙ АНАЛИЗ ПО ИСХОДАМ:
       - Сравните выписанных vs умерших по всем ключевым показателям
       - Используйте t-тесты для непрерывных переменных
       - χ² для категориальных
       - Рассчитайте effect sizes (Cohen's d)
    
    4. ПРЕДИКТОРЫ ЛЕТАЛЬНОСТИ:
       - Логистическая регрессия: предсказание исхода
       - Включите: возраст, SpO2, qSOFA, WBC, фибриноген, ЧДД
       - Оцените OR с 95% CI
    
    5. КОРРЕЛЯЦИОННЫЙ АНАЛИЗ:
       - Связь между маркерами воспаления (WBC, фибриноген, СРБ)
       - Связь гипоксии (SpO2) с тяжестью (qSOFA, ЧДД)
    
    Требования к отчёту:
    - Все таблицы с p-values и effect sizes
    - Графики: box plots для сравнений, correlation heatmap
    - Интерпретация на русском языке в академическом стиле
    """
    
    print("=" * 80)
    print("🧪 COPILOT E2E TEST: COVID-19 ANALYSIS")
    print("=" * 80)
    
    # Step 1: Create Plan
    print("\n📋 STEP 1: Creating Analysis Plan...")
    plan_result = await engine.create_plan(
        dataset_path=dataset_path,
        user_request=user_request,
        advanced=True
    )
    
    if not plan_result.get("success"):
        print(f"❌ Plan creation failed: {plan_result.get('error')}")
        return
    
    session_id = plan_result["session_id"]
    plan = plan_result["plan"]
    
    print(f"✅ Plan created (Session: {session_id[:8]}...)")
    print(f"\nUnderstood Goal: {plan.get('understood_goal', 'N/A')}")
    print(f"Domain: {plan.get('domain', 'N/A')}")
    print(f"Study Type: {plan.get('design', {}).get('study_type', 'N/A')}")
    print(f"Number of Analyses: {len(plan.get('analyses', []))}")
    
    # Step 2: Execute Plan
    print("\n⚙️ STEP 2: Executing Analysis Plan...")
    exec_result = await engine.execute_plan(session_id=session_id)
    
    if not exec_result.get("success"):
        print(f"❌ Execution failed: {exec_result.get('error')}")
        print(f"Output: {exec_result.get('output', 'N/A')[:500]}")
        return
    
    print("✅ Execution successful!")
    
    # Step 3: Generate Report
    print("\n📄 STEP 3: Generating DOCX Report...")
    from app.copilot.report import generate_report
    
    session = engine.sessions.get(session_id)
    if not session:
        print("❌ Session not found")
        return
    
    docx_bytes = generate_report(
        results=session.get("results", {}),
        plan=session.get("plan", {}),
        code=session.get("code"),
        interpretation=session.get("interpretation"),
        dataset_info=session.get("dataset_info", {})
    )
    
    report_path = f"workspace/covid19_report_{session_id[:8]}.docx"
    with open(report_path, "wb") as f:
        f.write(docx_bytes)
    
    print(f"✅ Report saved: {report_path}")
    print(f"   Size: {len(docx_bytes) / 1024:.1f} KB")
    
    # Step 4: Generate PDF
    print("\n📕 STEP 4: Generating PDF Report...")
    from app.copilot.pdf_exporter import docx_to_pdf
    
    try:
        pdf_bytes = docx_to_pdf(docx_bytes)
        pdf_path = f"workspace/covid19_report_{session_id[:8]}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"✅ PDF saved: {pdf_path}")
        print(f"   Size: {len(pdf_bytes) / 1024:.1f} KB")
    except Exception as e:
        print(f"⚠️ PDF generation failed: {e}")
    
    print("\n" + "=" * 80)
    print("🎉 TEST COMPLETE!")
    print("=" * 80)
    print(f"\nSession ID: {session_id}")
    print(f"DOCX Report: {report_path}")
    if 'pdf_path' in locals():
        print(f"PDF Report: {pdf_path}")

if __name__ == "__main__":
    asyncio.run(main())
