from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from ..environment_schemas import CurrentEnvironment
from ..services.environment_service import EnvironmentService, EnvironmentUnavailable, get_environment_service

router = APIRouter(prefix="/environment", tags=["Environment"])


@router.get("/current", response_model=CurrentEnvironment, responses={503: {"description": "Environmental data unavailable"}})
async def current_environment(
    response: Response,
    service: Annotated[EnvironmentService, Depends(get_environment_service)],
) -> CurrentEnvironment:
    response.headers["Cache-Control"] = "no-store"
    try:
        return await service.get_current()
    except EnvironmentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc), headers={"Cache-Control": "no-store"}) from exc
