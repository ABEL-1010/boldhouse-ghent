from fastapi import APIRouter, HTTPException, Request

from sentinel.features.gateway.decisions import NoPendingDecision
from sentinel.features.gateway.schemas import (
    DecisionRequest,
    DecisionResponse,
    ToolRequest,
    ToolResponse,
)
from sentinel.features.gateway.service import ApprovalReasonRequired, GatewayService

router = APIRouter(tags=["gateway"])


def get_gateway(request: Request) -> GatewayService:
    gateway: GatewayService = request.app.state.gateway
    return gateway


@router.post("/tool")
async def post_tool(body: ToolRequest, request: Request) -> ToolResponse:
    """Score a tool call and run it, or hold it for a human decision if it is high risk."""
    return await get_gateway(request).handle(body)


@router.post("/decision/{event_id}")
def post_decision(event_id: str, body: DecisionRequest, request: Request) -> DecisionResponse:
    """Approve or deny a paused action. Approving requires a written reason."""
    try:
        decision = get_gateway(request).decide(event_id, body)
    except NoPendingDecision as exc:
        raise HTTPException(404, "No pending action with this id.") from exc
    except ApprovalReasonRequired as exc:
        raise HTTPException(400, str(exc)) from exc
    return DecisionResponse(ok=True, decision=decision)
