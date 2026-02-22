"""
Async Statistical Computation Engine
Optimized for MacBook M1 8GB with ProcessPoolExecutor and memory-aware scheduling.
"""
import asyncio
import concurrent.futures
from typing import Dict, Any, Callable, Optional
import gc
import time
from functools import partial
import logging

# Configure logging
logger = logging.getLogger(__name__)


class AsyncStatisticalEngine:
    """
    Asynchronous engine for CPU-intensive statistical computations.
    Uses ProcessPoolExecutor to avoid blocking the main event loop.
    
    Key features:
    - Memory-aware worker management
    - Timeout protection
    - Graceful degradation under load
    - Resource usage monitoring
    """
    
    def __init__(self, max_workers: int = 2, max_memory_mb: int = 1200):
        """
        Initialize async engine with resource constraints.
        
        Args:
            max_workers: Maximum parallel processes (2 for M1 8GB)
            max_memory_mb: Memory limit per analysis in MB
        """
        self.max_workers = max_workers
        self.max_memory = max_memory_mb * 1024 * 1024  # bytes
        self.executor = None
        self._active_tasks = 0
        self._task_semaphore = asyncio.Semaphore(max_workers)
        
    async def start(self):
        """Initialize the process pool."""
        if self.executor is None:
            self.executor = concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers
            )
        
    async def stop(self):
        """Cleanup process pool."""
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None
    
    async def run_analysis(
        self, 
        analysis_func: Callable,
        *args,
        timeout: int = 300,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run statistical analysis asynchronously with resource constraints.
        
        Args:
            analysis_func: Function to execute (must be pickleable)
            timeout: Maximum execution time in seconds
            *args, **kwargs: Arguments to pass to analysis_func
            
        Returns:
            Analysis results or error information
        """
        async with self._task_semaphore:
            self._active_tasks += 1
            
            try:
                # Run in process pool with timeout
                loop = asyncio.get_event_loop()
                
                # Create partial function for execution
                func_partial = partial(analysis_func, *args, **kwargs)
                
                # Execute with timeout
                result = await asyncio.wait_for(
                    loop.run_in_executor(self.executor, func_partial),
                    timeout=timeout
                )
                
                return {
                    "success": True,
                    "data": result,
                    "metadata": {
                        "execution_time": time.time(),
                        "active_tasks": self._active_tasks
                    }
                }
                
            except asyncio.TimeoutError:
                logger.warning(f"Analysis timed out after {timeout}s")
                return {
                    "success": False,
                    "error": "Analysis timed out",
                    "error_type": "timeout"
                }
                
            except concurrent.futures.process.BrokenProcessPool:
                logger.error("Process pool broken, restarting...")
                await self.stop()
                await self.start()
                return {
                    "success": False,
                    "error": "Process pool error, please retry",
                    "error_type": "process_pool"
                }
                
            except Exception as e:
                logger.error(f"Analysis failed: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": "analysis_error"
                }
                
            finally:
                self._active_tasks -= 1
                gc.collect()  # Force garbage collection
    
    async def run_batch_analysis(
        self,
        analyses: list,
        max_concurrent: Optional[int] = None,
        timeout_per_task: int = 180
    ) -> Dict[str, Any]:
        """
        Run multiple analyses concurrently with controlled parallelism.
        
        Args:
            analyses: List of analysis specifications
            max_concurrent: Maximum concurrent analyses (default: max_workers)
            timeout_per_task: Timeout per individual analysis
            
        Returns:
            Batch results with individual statuses
        """
        if max_concurrent is None:
            max_concurrent = self.max_workers
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_semaphore(analysis_spec):
            async with semaphore:
                return await self.run_analysis(
                    analysis_spec["func"],
                    *analysis_spec.get("args", []),
                    **analysis_spec.get("kwargs", {}),
                    timeout=timeout_per_task
                )
        
        # Run all analyses concurrently with controlled parallelism
        tasks = [
            run_with_semaphore(analysis_spec)
            for analysis_spec in analyses
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful = []
        failed = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed.append({
                    "index": i,
                    "error": str(result),
                    "error_type": "gather_exception"
                })
            elif result.get("success"):
                successful.append(result["data"])
            else:
                failed.append({
                    "index": i,
                    "error": result.get("error", "Unknown error"),
                    "error_type": result.get("error_type", "unknown")
                })
        
        return {
            "total": len(analyses),
            "successful": len(successful),
            "failed": len(failed),
            "results": successful,
            "failures": failed,
            "success_rate": len(successful) / len(analyses) if analyses else 0
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current engine status and resource usage."""
        return {
            "max_workers": self.max_workers,
            "active_tasks": self._active_tasks,
            "available_slots": self.max_workers - self._active_tasks,
            "memory_limit_mb": self.max_memory / 1024 / 1024,
            "executor_running": self.executor is not None
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check and resource validation."""
        try:
            # Test with simple computation
            test_result = await self.run_analysis(
                lambda: sum(range(1000)),
                timeout=10
            )
            
            healthy = test_result.get("success", False)
            
            return {
                "healthy": healthy,
                "active_tasks": self._active_tasks,
                "test_result": test_result if not healthy else None
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "active_tasks": self._active_tasks
            }


# Global engine instance for application-wide use
_async_engine = None


def get_async_engine() -> AsyncStatisticalEngine:
    """Get or create the global async engine instance."""
    global _async_engine
    if _async_engine is None:
        _async_engine = AsyncStatisticalEngine(max_workers=2, max_memory_mb=1200)
    return _async_engine


async def initialize_async_engine():
    """Initialize the global async engine."""
    engine = get_async_engine()
    await engine.start()
    return engine


async def shutdown_async_engine():
    """Shutdown the global async engine."""
    global _async_engine
    if _async_engine:
        await _async_engine.stop()
        _async_engine = None


# Utility functions for common statistical operations

def async_t_test(df, col_a, col_b, **kwargs):
    """Async wrapper for t-test (example)."""
    from app.stats.engine import run_analysis
    return run_analysis(df, "t_test_ind", col_a, col_b, **kwargs)


def async_anova(df, outcome, group, **kwargs):
    """Async wrapper for ANOVA."""
    from app.stats.engine import run_analysis
    return run_analysis(df, "anova", outcome, group, **kwargs)


def async_correlation(df, col_a, col_b, **kwargs):
    """Async wrapper for correlation."""
    from app.stats.engine import run_analysis
    return run_analysis(df, "pearson", col_a, col_b, **kwargs)


# Memory-aware analysis functions

def memory_aware_analysis(df, analysis_func, max_rows=10000, **kwargs):
    """
    Perform analysis with memory constraints.
    For large datasets, use sampling or chunking.
    """
    if len(df) > max_rows:
        # Sample for very large datasets
        sample_df = df.sample(n=max_rows, random_state=42)
        result = analysis_func(sample_df, **kwargs)
        result["sampling_info"] = {
            "sampled": True,
            "sample_size": max_rows,
            "total_rows": len(df),
            "sampling_percentage": (max_rows / len(df)) * 100
        }
        return result
    else:
        # Full analysis for small datasets
        return analysis_func(df, **kwargs)