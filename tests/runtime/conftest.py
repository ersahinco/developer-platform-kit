from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-runtime-conformance",
        action="store_true",
        default=False,
        help="Build and run workload containers against the portable runtime contract.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-runtime-conformance"):
        return
    skip = pytest.mark.skip(reason="requires --run-runtime-conformance")
    for item in items:
        if "tests/runtime" in str(item.path):
            item.add_marker(skip)
