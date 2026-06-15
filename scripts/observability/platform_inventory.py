from __future__ import annotations

import sys

from scripts.platform.workload_evidence import edge_symptom_alarm_names


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != "edge-symptom-alarms":
        print(
            "usage: python -m scripts.observability.platform_inventory "
            "edge-symptom-alarms <stack-name>",
            file=sys.stderr,
        )
        return 1

    _, stack_name = argv
    for alarm_name in edge_symptom_alarm_names(stack_name):
        print(alarm_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
