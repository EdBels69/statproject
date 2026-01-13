"""
Streaming Results API for Large Statistical Analyses
Optimized for memory-constrained environments with progressive result delivery.
"""
import asyncio
import json
from typing import Dict, Any, AsyncGenerator, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import gc
import time
from datetime import datetime

from app.stats.async_engine import get_async_engine
from app.schemas.analysis import AnalysisRequest

router = APIRouter(prefix="/stream", tags=["streaming"])


class StreamingAnalysisEngine:
    """Engine for streaming large analysis results in chunks."""
    
    def __init__(self, chunk_size: int = 1000, max_chunks: int = 1000):
        self.chunk_size = chunk_size  # Results per chunk
        self.max_chunks = max_chunks  # Safety limit
    
    async def stream_analysis(
        self, 
        analysis_func: callable,
        *args,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream analysis results in chunks to avoid memory overload.
        
        Yields:
            JSON chunks of results with progress metadata
        """
        start_time = time.time()
        chunks_sent = 0
        
        try:
            # Run analysis asynchronously
            engine = get_async_engine()
            result = await engine.run_analysis(analysis_func, *args, **kwargs)
            
            if not result.get("success"):
                yield self._create_error_chunk(result.get("error", "Analysis failed"))
                return
            
            analysis_data = result["data"]
            
            # Stream results based on type
            if isinstance(analysis_data, dict):
                # Single result - send as one chunk
                yield self._create_result_chunk(analysis_data, 1, 1, start_time)
                
            elif isinstance(analysis_data, list):
                # Multiple results - stream in chunks
                total_items = len(analysis_data)
                
                for i in range(0, total_items, self.chunk_size):
                    if chunks_sent >= self.max_chunks:
                        yield self._create_error_chunk("Maximum chunk limit exceeded")
                        break
                        
                    chunk = analysis_data[i:i + self.chunk_size]
                    chunks_sent += 1
                    
                    yield self._create_result_chunk(
                        chunk, 
                        chunks_sent,
                        (total_items + self.chunk_size - 1) // self.chunk_size,
                        start_time
                    )
                    
                    # Small delay to prevent overwhelming client
                    await asyncio.sleep(0.01)
                    gc.collect()
            
            # Final completion chunk
            yield self._create_completion_chunk(start_time, chunks_sent or 1)
            
        except Exception as e:
            yield self._create_error_chunk(f"Streaming error: {str(e)}")
    
    def _create_result_chunk(
        self, 
        data: Any, 
        chunk_num: int, 
        total_chunks: int,
        start_time: float
    ) -> str:
        """Create a JSON chunk with result data and progress metadata."""
        chunk = {
            "type": "data",
            "chunk": chunk_num,
            "total_chunks": total_chunks,
            "progress": min(100, int((chunk_num / total_chunks) * 100)),
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "elapsed_seconds": round(time.time() - start_time, 2)
        }
        return json.dumps(chunk) + "\n"
    
    def _create_completion_chunk(self, start_time: float, total_chunks: int) -> str:
        """Create completion signal chunk."""
        chunk = {
            "type": "complete",
            "total_chunks": total_chunks,
            "timestamp": datetime.utcnow().isoformat(),
            "elapsed_seconds": round(time.time() - start_time, 2),
            "memory_cleared": True
        }
        return json.dumps(chunk) + "\n"
    
    def _create_error_chunk(self, error_message: str) -> str:
        """Create error chunk."""
        chunk = {
            "type": "error",
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }
        return json.dumps(chunk) + "\n"


# Global streaming engine instance
_streaming_engine = StreamingAnalysisEngine()


@router.post("/analysis")
async def stream_analysis(request: AnalysisRequest):
    """
    Stream analysis results for large datasets.
    
    Returns NDJSON stream with progress updates.
    """
    from app.stats.engine import run_analysis
    
    # Validate request
    if not request.dataset_id or not request.protocol:
        raise HTTPException(status_code=400, detail="Missing dataset_id or protocol")
    
    # Create streaming response
    return StreamingResponse(
        _streaming_engine.stream_analysis(
            run_analysis,
            request.dataset_id,
            request.protocol,
            **request.dict(exclude={"dataset_id", "protocol"})
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Connection": "keep-alive"
        }
    )


@router.get("/health")
async def streaming_health():
    """Health check for streaming service."""
    return {
        "status": "healthy", 
        "chunk_size": _streaming_engine.chunk_size,
        "max_chunks": _streaming_engine.max_chunks,
        "timestamp": datetime.utcnow().isoformat()
    }


# Utility function for frontend streaming consumption

def create_ndjson_stream(data: list, chunk_size: int = 100) -> AsyncGenerator[str, None]:
    """
    Create NDJSON stream from data list.
    
    Args:
        data: List of items to stream
        chunk_size: Items per chunk
        
    Yields:
        NDJSON formatted chunks
    """
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        yield json.dumps({
            "chunk": i // chunk_size + 1,
            "total_chunks": (len(data) + chunk_size - 1) // chunk_size,
            "data": chunk,
            "progress": min(100, int((i + chunk_size) / len(data) * 100))
        }) + "\n"
        
        # Yield control to event loop
        await asyncio.sleep(0.001)


# Memory-efficient large result processing

def process_large_results_in_chunks(
    results: list, 
    process_func: callable, 
    chunk_size: int = 500
) -> list:
    """
    Process large results in memory-efficient chunks.
    
    Args:
        results: Large list of results
        process_func: Function to apply to each chunk
        chunk_size: Size of processing chunks
        
    Returns:
        Processed results
    """
    processed = []
    
    for i in range(0, len(results), chunk_size):
        chunk = results[i:i + chunk_size]
        processed_chunk = process_func(chunk)
        processed.extend(processed_chunk)
        
        # Clear memory between chunks
        del chunk
        gc.collect()
    
    return processed