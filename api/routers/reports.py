"""Scorecard / reports endpoint."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends

from api.config import Settings
from api.dependencies import get_settings
from api.schemas import Scorecard

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/scorecard", response_model=Scorecard)
def get_scorecard(settings: Settings = Depends(get_settings)):
    path = Path(settings.scorecard_path)
    if not path.is_file():
        return Scorecard()
    try:
        data = json.loads(path.read_text())
        return Scorecard(**data)
    except Exception:
        return Scorecard()
