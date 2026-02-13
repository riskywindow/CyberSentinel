"""Evaluation job manager — background thread runner for eval/harness.py."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvalJob:
    run_id: str
    status: str = "queued"       # queued | running | completed | failed
    scorecard: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    _thread: Optional[threading.Thread] = field(default=None, repr=False)


class EvalJobManager:
    """Simple in-memory job tracker backed by daemon threads."""

    def __init__(self, scenarios_path: str, output_path: str,
                 scorecard_path: str) -> None:
        self.scenarios_path = scenarios_path
        self.output_path = output_path
        self.scorecard_path = scorecard_path
        self._jobs: Dict[str, EvalJob] = {}
        self._lock = threading.Lock()

    def enqueue(self, seed: int = 42) -> str:
        """Spawn a background harness run and return the run_id."""
        run_id = uuid.uuid4().hex[:12]
        job = EvalJob(run_id=run_id)

        def _run() -> None:
            job.status = "running"
            try:
                result = subprocess.run(
                    [
                        sys.executable, "eval/harness.py",
                        "--scenarios", self.scenarios_path,
                        "--output", self.output_path,
                        "--seed", str(seed),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode == 0:
                    job.status = "completed"
                    try:
                        with open(self.scorecard_path) as f:
                            job.scorecard = json.load(f)
                    except Exception:
                        pass
                else:
                    job.status = "failed"
                    job.error = result.stderr or result.stdout
            except subprocess.TimeoutExpired:
                job.status = "failed"
                job.error = "Harness timed out after 600 s"
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)

        t = threading.Thread(target=_run, daemon=True)
        job._thread = t

        with self._lock:
            self._jobs[run_id] = job

        t.start()
        return run_id

    def get_status(self, run_id: str) -> Optional[EvalJob]:
        with self._lock:
            return self._jobs.get(run_id)
