from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "platform" / "concerns" / "policy" / "conftest"
POLICY_IMAGE = "openpolicyagent/conftest:v0.64.0"


def _run_conftest(*targets: Path, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    relative_targets = []
    for target in targets:
        try:
            relative_targets.append(str(target.relative_to(cwd)))
        except ValueError:
            relative_targets = []
            break

    conftest_binary = subprocess.run(
        ["bash", "-lc", "command -v conftest"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if conftest_binary.returncode == 0:
        return subprocess.run(
            [
                conftest_binary.stdout.strip(),
                "test",
                "--policy",
                str(POLICY_DIR),
                *(relative_targets or [str(target) for target in targets]),
            ],
            capture_output=True,
            text=True,
            cwd=cwd,
        )

    docker_args = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{ROOT}:/project",
        "-w",
        "/project",
    ]

    if cwd != ROOT:
        docker_args.extend(["-v", f"{cwd}:/fixtures"])
        mounted_targets = [f"/fixtures/{target.name}" for target in targets]
    else:
        mounted_targets = [str(target.relative_to(ROOT)) for target in targets]

    return subprocess.run(
        [
            *docker_args,
            POLICY_IMAGE,
            "test",
            "--policy",
            "platform/concerns/policy/conftest",
            *mounted_targets,
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def test_current_contract_surfaces_pass_policy_checks() -> None:
    workflow_paths = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    completed = _run_conftest(
        *workflow_paths,
        ROOT / "platform" / "workloads.json",
        ROOT / "platform" / "runtime-conformance.json",
        ROOT / "platform" / "platform-inventory.json",
        ROOT / "platform" / "runtime-defaults.json",
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_workload_contract_policy_rejects_runtime_without_support(
    tmp_path: Path,
) -> None:
    workload_contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    invalid = dict(workload_contract)
    invalid["workloads"] = [dict(workload_contract["workloads"][0])]
    invalid["workloads"][0]["runtime"] = {
        "supported": ["local-compose"],
        "admitted": ["aws-ecs"],
    }
    fixture = tmp_path / "workloads.json"
    fixture.write_text(json.dumps(invalid), encoding="utf-8")

    completed = _run_conftest(fixture, cwd=tmp_path)

    assert completed.returncode != 0
    assert "admits runtime" in (completed.stderr + completed.stdout)


def test_workload_contract_policy_rejects_workload_patterns(
    tmp_path: Path,
) -> None:
    workload_contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    invalid = dict(workload_contract)
    invalid["workloads"] = [dict(workload_contract["workloads"][0])]
    invalid["workloads"][0]["patterns"] = ["edge-service"]
    fixture = tmp_path / "workloads.json"
    fixture.write_text(json.dumps(invalid), encoding="utf-8")

    completed = _run_conftest(fixture, cwd=tmp_path)

    assert completed.returncode != 0
    assert "must not declare patterns" in (completed.stderr + completed.stdout)


def test_workload_contract_policy_rejects_deployment_choreography_fields(
    tmp_path: Path,
) -> None:
    workload_contract = json.loads((ROOT / "platform" / "workloads.json").read_text())
    invalid = dict(workload_contract)
    invalid["workloads"] = [dict(workload_contract["workloads"][0])]
    invalid["workloads"][0]["ecs"] = {"desired_count": 2}
    fixture = tmp_path / "workloads.json"
    fixture.write_text(json.dumps(invalid), encoding="utf-8")

    completed = _run_conftest(fixture, cwd=tmp_path)

    assert completed.returncode != 0
    assert "must not encode deployment choreography key" in (
        completed.stderr + completed.stdout
    )


def test_runtime_conformance_policy_rejects_workload_shape_fields(
    tmp_path: Path,
) -> None:
    runtime_conformance = json.loads(
        (ROOT / "platform" / "runtime-conformance.json").read_text()
    )
    invalid = dict(runtime_conformance)
    invalid["workloads"] = {
        "api": {
            "startup_timeout_seconds": 30,
            "service": {"port": 8000},
        }
    }
    fixture = tmp_path / "runtime-conformance.json"
    fixture.write_text(json.dumps(invalid), encoding="utf-8")

    completed = _run_conftest(fixture, cwd=tmp_path)

    assert completed.returncode != 0
    assert "must not redefine workload field" in (completed.stderr + completed.stdout)


def test_platform_inventory_policy_rejects_wrong_stable_center(tmp_path: Path) -> None:
    platform_inventory = json.loads(
        (ROOT / "platform" / "platform-inventory.json").read_text()
    )
    invalid = dict(platform_inventory)
    invalid["stable_center"] = {
        "workload_contract": "platform/workloads.json",
        "platform_concerns_root": "platform/wrong",
        "catalog_root": "infra/catalog",
    }
    fixture = tmp_path / "platform-inventory.json"
    fixture.write_text(json.dumps(invalid), encoding="utf-8")

    completed = _run_conftest(fixture, cwd=tmp_path)

    assert completed.returncode != 0
    assert "stable_center.platform_concerns_root must be platform/concerns" in (
        completed.stderr + completed.stdout
    )


def test_platform_inventory_policy_rejects_candidate_capability_owner(
    tmp_path: Path,
) -> None:
    platform_inventory = json.loads(
        (ROOT / "platform" / "platform-inventory.json").read_text()
    )
    invalid = dict(platform_inventory)
    invalid["candidate_runtime_capabilities"] = []
    fixture = tmp_path / "platform-inventory.json"
    fixture.write_text(json.dumps(invalid), encoding="utf-8")

    completed = _run_conftest(fixture, cwd=tmp_path)

    assert completed.returncode != 0
    assert "must not own candidate_runtime_capabilities" in (
        completed.stderr + completed.stdout
    )


def test_platform_inventory_policy_rejects_default_capability_owner(
    tmp_path: Path,
) -> None:
    platform_inventory = json.loads(
        (ROOT / "platform" / "platform-inventory.json").read_text()
    )
    invalid = dict(platform_inventory)
    invalid["runtime_capabilities"] = [
        *platform_inventory["runtime_capabilities"],
        {
            "capability": "edge_auth",
            "contract_surface": "default auth",
            "runtime_target": "local-compose",
            "maturity": "active-local-proof",
            "implementation": "duplicate default",
            "replacement_seam": "platform/runtime-defaults.json",
        },
    ]
    fixture = tmp_path / "platform-inventory.json"
    fixture.write_text(json.dumps(invalid), encoding="utf-8")

    completed = _run_conftest(fixture, cwd=tmp_path)

    assert completed.returncode != 0
    assert "must not own runtime default capability" in (
        completed.stderr + completed.stdout
    )


def test_runtime_defaults_policy_rejects_unknown_current_target(
    tmp_path: Path,
) -> None:
    runtime_defaults = json.loads(
        (ROOT / "platform" / "runtime-defaults.json").read_text()
    )
    invalid = dict(runtime_defaults)
    invalid["current_runtime_target"] = "missing-runtime"
    fixture = tmp_path / "runtime-defaults.json"
    fixture.write_text(json.dumps(invalid), encoding="utf-8")

    completed = _run_conftest(fixture, cwd=tmp_path)

    assert completed.returncode != 0
    assert "current_runtime_target must name an active runtime target" in (
        completed.stderr + completed.stdout
    )


def test_workflow_policy_rejects_continue_on_error(tmp_path: Path) -> None:
    fixture = tmp_path / "app-deploy.yml"
    fixture.write_text(
        yaml.safe_dump(
            {
                "name": "App Deploy",
                "on": {"workflow_dispatch": None},
                "jobs": {
                    "deploy": {
                        "environment": "aws",
                        "runs-on": "ubuntu-latest",
                        "steps": [
                            {
                                "name": "Upload app deploy evidence",
                                "run": "echo ok",
                                "continue-on-error": True,
                            }
                        ],
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    completed = _run_conftest(fixture, cwd=tmp_path)

    assert completed.returncode != 0
    assert "must not use continue-on-error" in (completed.stderr + completed.stdout)
