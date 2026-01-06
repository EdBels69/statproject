from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.modules.protocol_agent import ProtocolAgent

router = APIRouter()
agent = ProtocolAgent()

class ProtocolRequest(BaseModel):
    description: str

class ProtocolResponse(BaseModel):
    nodes: list
    edges: list

@router.post("/generate", response_model=ProtocolResponse)
def generate_protocol(request: ProtocolRequest):
    """
    Generates a visual protocol graph from natural language description.
    """
    try:
        graph = agent.parse_instruction(request.description)
        return graph
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
