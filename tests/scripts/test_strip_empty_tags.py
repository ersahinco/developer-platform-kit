from __future__ import annotations

import json
from pathlib import Path

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from scripts.ci.ci_strip_empty_tags import strip_empty_tags


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_strip_empty_tags_removes_key_when_tags_is_empty_list(tmp_path: Path) -> None:
    """tags: [] → key removed from output file."""
    task_def = tmp_path / "task.json"
    _write_json(task_def, {"family": "my-task", "tags": []})

    strip_empty_tags(task_def)

    result = _read_json(task_def)
    assert isinstance(result, dict)
    assert "tags" not in result
    assert result.get("family") == "my-task"


def test_strip_empty_tags_preserves_key_when_tags_is_non_empty(tmp_path: Path) -> None:
    """tags: [{"key": "env", "value": "prod"}] → key preserved unchanged."""
    tags = [{"key": "env", "value": "prod"}]
    task_def = tmp_path / "task.json"
    _write_json(task_def, {"family": "my-task", "tags": tags})

    strip_empty_tags(task_def)

    result = _read_json(task_def)
    assert isinstance(result, dict)
    assert result["tags"] == tags
    assert result.get("family") == "my-task"


def test_strip_empty_tags_writes_file_unchanged_when_no_tags_key(
    tmp_path: Path,
) -> None:
    """No tags key present → file written back unchanged."""
    original = {"family": "my-task", "containerDefinitions": [{"name": "app"}]}
    task_def = tmp_path / "task.json"
    _write_json(task_def, original)

    strip_empty_tags(task_def)

    result = _read_json(task_def)
    assert result == original


_json_primitive = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31 - 1),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=20),
)

_tags_strategy = st.one_of(
    st.just([]),  # empty list — the key case
    st.lists(_json_primitive, min_size=1, max_size=3),  # non-empty list
)

_task_definition_strategy = st.fixed_dictionaries(
    {},
    optional={
        "family": st.text(max_size=20),
        "tags": _tags_strategy,
        "containerDefinitions": st.lists(
            st.dictionaries(st.text(max_size=10), _json_primitive, max_size=3),
            max_size=2,
        ),
        "cpu": st.text(max_size=5),
        "memory": st.text(max_size=5),
    },
)


@given(task_def=_task_definition_strategy)
@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_strip_empty_tags_is_idempotent(task_def: dict, tmp_path: Path) -> None:
    """Calling strip_empty_tags twice produces the same file content."""
    path = tmp_path / "task.json"
    path.write_text(json.dumps(task_def, indent=2) + "\n", encoding="utf-8")

    strip_empty_tags(path)
    contents_after_first = path.read_text(encoding="utf-8")

    strip_empty_tags(path)
    contents_after_second = path.read_text(encoding="utf-8")

    assert contents_after_first == contents_after_second


_non_empty_tags_strategy = st.lists(
    st.one_of(
        st.dictionaries(st.text(max_size=10), st.text(max_size=20), max_size=3),
        _json_primitive,
    ),
    min_size=1,
    max_size=5,
)

_task_definition_no_empty_tags_strategy = st.fixed_dictionaries(
    {},
    optional={
        "family": st.text(max_size=20),
        "tags": _non_empty_tags_strategy,  # only non-empty lists when present
        "containerDefinitions": st.lists(
            st.dictionaries(st.text(max_size=10), _json_primitive, max_size=3),
            max_size=2,
        ),
        "cpu": st.text(max_size=5),
        "memory": st.text(max_size=5),
    },
)


@given(task_def=_task_definition_no_empty_tags_strategy)
@settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_strip_empty_tags_preserves_non_empty_or_absent_tags(
    task_def: dict, tmp_path: Path
) -> None:
    """Non-empty tags stay unchanged, and absent tags stay absent."""
    path = tmp_path / "task.json"
    path.write_text(json.dumps(task_def, indent=2) + "\n", encoding="utf-8")

    tags_before = task_def.get("tags", "__ABSENT__")

    strip_empty_tags(path)

    result = json.loads(path.read_text(encoding="utf-8"))

    if tags_before == "__ABSENT__":
        assert "tags" not in result
    else:
        assert result["tags"] == tags_before


_any_tags_strategy = st.one_of(
    st.just([]),
    st.lists(
        st.one_of(
            st.dictionaries(st.text(max_size=10), st.text(max_size=20), max_size=3),
            _json_primitive,
        ),
        min_size=1,
        max_size=5,
    ),
)

_task_definition_any_tags_strategy = st.fixed_dictionaries(
    {},
    optional={
        "family": st.text(max_size=20),
        "tags": _any_tags_strategy,
        "containerDefinitions": st.lists(
            st.dictionaries(st.text(max_size=10), _json_primitive, max_size=3),
            max_size=2,
        ),
        "cpu": st.text(max_size=5),
        "memory": st.text(max_size=5),
        "executionRoleArn": st.text(max_size=30),
        "taskRoleArn": st.text(max_size=30),
    },
)


@given(task_def=_task_definition_any_tags_strategy)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_strip_empty_tags_preserves_all_non_tags_fields(
    task_def: dict, tmp_path: Path
) -> None:
    """Only the tags field may change after stripping."""
    path = tmp_path / "task.json"
    path.write_text(json.dumps(task_def, indent=2) + "\n", encoding="utf-8")

    strip_empty_tags(path)

    result = json.loads(path.read_text(encoding="utf-8"))

    for key, value in task_def.items():
        if key == "tags":
            continue
        assert key in result, f"Field {key!r} was lost after strip_empty_tags"
        assert result[key] == value, (
            f"Field {key!r} was mutated: expected {value!r}, got {result[key]!r}"
        )

    non_tags_keys = {k for k in task_def if k != "tags"}
    tags_in_input = "tags" in task_def
    tags_is_empty = task_def.get("tags") == []
    expected_keys = non_tags_keys | (
        {"tags"} if tags_in_input and not tags_is_empty else set()
    )
    assert set(result.keys()) == expected_keys, (
        f"Unexpected keys in output: {set(result.keys()) - expected_keys}"
    )
