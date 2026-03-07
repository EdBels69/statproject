"""
Simplified COVID E2E Test - Focused Analysis
"""
import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.copilot.engine import CopilotEngine

async def main():
    engine = CopilotEngine()
    
    dataset_path = os.path.abspath("workspace/covid19_dataset.csv")
    
    # Simplified, focused prompt
    user_request = """
    Проведите базовый анализ пациентов с COVID-19:
    
    1. Описательная статистика по возрасту, полу, длительности госпитализации
    2. Сравнение выписанных vs умерших по ключевым показателям:
       - Возраст
       - SpO2 при поступлении
       - Лейкоциты (WBC)
    3. Используйте t-тесты и рассчитайте Cohen's d
    """
    
    print("🧪 SIMPLIFIED COVID-19 TEST")
    print("=" * 60)
    
    # Create Plan
    print("\n📋 Creating Plan...")
    import uuid
    import pandas as pd
    
    session_id = str(uuid.uuid4())
    df = pd.read_csv(dataset_path)
    dataset_info = {
        "filename": os.path.basename(dataset_path),
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "columns": list(df.columns),
        "dataset_meta": {"summary": {"n_rows": len(df), "columns": list(df.columns)}}
    }
    
    plan_result = await engine.create_plan(
        session_id=session_id,
        user_request=user_request,
        dataset_path=dataset_path,
        dataset_info=dataset_info,
        advanced=True
    )
    
    if not plan_result.get("success"):
        print(f"❌ Failed: {plan_result.get('error')}")
        return
    
    session_id = plan_result["session_id"]
    print(f"✅ Plan OK (Session: {session_id[:8]})")
    print(f"Goal: {plan_result['plan'].get('understood_goal', 'N/A')[:100]}...")
    
    # Execute
    print("\n⚙️ Executing...")
    exec_result = await engine.execute_plan(session_id=session_id)
    
    if not exec_result.get("success"):
        print(f"❌ Execution failed: {exec_result.get('error')}")
        return
    
    print("✅ Execution OK!")
    
    # Generate Report
    print("\n📄 Generating Report...")
    from app.copilot.report import generate_report
    
    session = engine.sessions.get(session_id)
    docx_bytes = generate_report(
        results=session.get("results", {}),
        plan=session.get("plan", {}),
        code=session.get("code"),
        dataset_info=session.get("dataset_info", {})
    )
    
    report_path = f"workspace/covid_simple_{session_id[:8]}.docx"
    with open(report_path, "wb") as f:
        f.write(docx_bytes)
    
    print(f"✅ Report: {report_path} ({len(docx_bytes)/1024:.1f} KB)")
    
    # Try PDF
    try:
        from app.copilot.pdf_exporter import docx_to_pdf
        pdf_bytes = docx_to_pdf(docx_bytes)
        pdf_path = f"workspace/covid_simple_{session_id[:8]}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"✅ PDF: {pdf_path} ({len(pdf_bytes)/1024:.1f} KB)")
    except Exception as e:
        print(f"⚠️ PDF failed: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 TEST COMPLETE!")

if __name__ == "__main__":
    asyncio.run(main())
