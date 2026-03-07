"""Test Copilot with real LLM"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.copilot.engine import CopilotEngine

async def test():
    engine = CopilotEngine()
    
    print("Testing Copilot with Qwen3-Next-80B...")
    print(f"Model: {engine.model}\n")
    
    # Simple test
    result = await engine.analyze(
        dataset_path='workspace/datasets/c8280bcd-20a3-4d61-8814-a216169d7919/processed/c8280bcd-20a3-4d61-8814-a216169d7919.parquet',
        user_request='Сравни группы по возрасту'
    )
    
    if result['success']:
        print('✅ SUCCESS!')
        print(f'\nПлан:')
        print(f"  Цель: {result['plan'].get('understood_goal', 'N/A')[:100]}")
        print(f"  Анализы: {len(result['plan'].get('analyses', []))}")
        print(f'\nКод сгенерирован: {len(result.get("code", ""))} символов')
        print(f'Результаты: {bool(result.get("results"))}')
    else:
        print('❌ FAILED')
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test())
