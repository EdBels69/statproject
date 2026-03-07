"""Quick test of Copilot engine."""
import asyncio
import sys
sys.path.insert(0, '.')

from app.copilot.engine import CopilotEngine

async def test():
    engine = CopilotEngine()
    
    # Test with Первичка dataset
    result = await engine.analyze(
        dataset_path='workspace/datasets/c8280bcd-20a3-4d61-8814-a216169d7919/processed/c8280bcd-20a3-4d61-8814-a216169d7919.parquet',
        user_request='Сравни 4 группы по переменной Группа. Проверь есть ли разница в возрасте между группами.'
    )
    
    if result['success']:
        print('✅ SUCCESS!')
        print(f'Session ID: {result["session_id"]}')
        print(f"\nПлан понят:")
        print(f"  Цель: {result['plan'].get('understood_goal', 'N/A')}")
        print(f"  Группа: {result['plan'].get('group_col', 'N/A')}")
        print(f"  Анализы: {len(result['plan'].get('analyses', []))}")
        print(f"\nКод сгенерирован: {len(result.get('code', ''))} символов")
        print(f"\nРезультаты: {len(str(result.get('results', {})))} символов")
        if result.get('interpretation'):
            print(f"\nИнтерпретация: {result['interpretation'][:200]}...")
    else:
        print('❌ FAILED')
        print(f"Error: {result.get('error')}")
        if result.get('raw_response'):
            print(f"Raw: {result['raw_response'][:500]}")

if __name__ == "__main__":
    asyncio.run(test())
