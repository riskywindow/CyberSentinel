"""Evaluation / replay endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.config import Settings
from api.dependencies import get_settings
from api.schemas import ReplayRequest, ReplayResponse, ReplayStatus
from api.services.eval_svc import EvalJobManager

router = APIRouter(prefix="/evaluate", tags=["evaluate"])

# Module-level singleton — initialised lazily on first request.
_manager: EvalJobManager | None = None


def _get_manager(settings: Settings = Depends(get_settings)) -> EvalJobManager:
    global _manager
    if _manager is None:
        _manager = EvalJobManager(
            scenarios_path=settings.eval_scenarios_path,
            output_path=settings.eval_output_path,
            scorecard_path=settings.scorecard_path,
        )
    return _manager


@router.post("/replay", response_model=ReplayResponse)
def start_replay(body: ReplayRequest,
                 manager: EvalJobManager = Depends(_get_manager)):
    run_id = manager.enqueue(seed=body.seed)
    return ReplayResponse.model_validate({"runId": run_id, "status": "queued"})


@router.get("/replay/{run_id}", response_model=ReplayStatus)
def get_replay_status(run_id: str,
                      manager: EvalJobManager = Depends(_get_manager)):
    job = manager.get_status(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return ReplayStatus.model_validate({
        "runId": job.run_id,
        "status": job.status,
        "scorecard": job.scorecard,
        "error": job.error,
    })
