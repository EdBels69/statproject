
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())
try:
    from app.copilot.r_engine import RExecutor
except ImportError as e:
    print(f"Could not import RExecutor: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

async def test_r():
    print("Testing RExecutor...")
    r_exec = RExecutor()
    print(f"Rscript path: {r_exec.rscript_path}")
    
    code = """
    x <- c(1, 2, 3, 4, 5)
    mean_x <- mean(x)
    print(paste("Mean is:", mean_x))
    """
    
    # Dummy dataset path
    dataset_path = "/tmp/test.csv"
    
    stdout, stderr = await r_exec.execute_code(code, dataset_path)
    
    print("--- STDOUT ---")
    print(stdout)
    print("--- STDERR ---")
    print(stderr)
    
    if "Mean is: 3" in stdout:
        print("SUCCESS: R code executed correctly.")
    else:
        print("FAILURE: R code did not produce expected output.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_r())
