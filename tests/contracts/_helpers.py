from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_json(path: str) -> dict[str, Any]:
    data = json.loads(read_text(path))
    assert isinstance(data, dict)
    return data


def load_yaml(path: str) -> dict[str, Any]:
    data = yaml.load(read_text(path), Loader=yaml.BaseLoader)
    assert isinstance(data, dict)
    return data


def load_workflow(path: str) -> dict[str, Any]:
    workflow = load_yaml(path)
    raw_workflow: dict[Any, Any] = workflow
    on_section = raw_workflow.pop(True, None)
    if on_section is not None and "on" not in workflow:
        workflow["on"] = on_section
    return workflow


def workflow_job(workflow: dict[str, Any], job_name: str) -> dict[str, Any]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    return job


def step_names(job: dict[str, Any]) -> list[str]:
    return [step.get("name", "") for step in job.get("steps", [])]


def step_run_text(job: dict[str, Any]) -> str:
    return "\n".join(step.get("run", "") for step in job.get("steps", []))


def has_markdown_link(text: str, target_fragment: str) -> bool:
    pattern = rf"\[[^\]]+\]\([^)]*{re.escape(target_fragment)}\)"
    return re.search(pattern, text) is not None
