"""Detection rule endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_settings
from api.config import Settings
from api.services import detection_svc

router = APIRouter(prefix="/detections", tags=["detections"])


@router.get("")
def list_detections(settings: Settings = Depends(get_settings)):
    return detection_svc.list_rules(settings.sigma_rules_dir)


@router.get("/{rule_id}")
def get_detection(rule_id: str, settings: Settings = Depends(get_settings)):
    rule = detection_svc.get_rule(settings.sigma_rules_dir, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Detection rule not found")
    return rule
