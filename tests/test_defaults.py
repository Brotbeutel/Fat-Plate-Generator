"""Repository defaults must resolve to the checked-in assets."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import fat_plate_generator as fpg
from tests.conftest import REPO_ROOT, build_model


DEFAULT_PATHS = (
    fpg.DEFAULT_JSON,
    fpg.DEFAULT_SOCKET,
    fpg.DEFAULT_SOCKET_WIDE_CAPS,
    fpg.DEFAULT_STABILIZER_2U,
    fpg.DEFAULT_SPACEBAR_6U_CENTERED,
    fpg.DEFAULT_SPACEBAR_6U_OFF_CENTERED,
    fpg.DEFAULT_SPACEBAR_6_25U_CENTERED,
    fpg.DEFAULT_SPACEBAR_6_25U_OFF_CENTERED,
    fpg.DEFAULT_SPACEBAR_7U_CENTERED,
)


@pytest.mark.parametrize("relative_path", DEFAULT_PATHS)
def test_default_path_exists_with_exact_repository_case(relative_path):
    path = Path(relative_path)
    current = REPO_ROOT
    for component in path.parts:
        entries = os.listdir(current)
        assert component in entries, (
            f"{relative_path!r}: path component {component!r} not found "
            f"with exact case in {current}"
        )
        current = current / component
    assert current.is_file(), f"Default file does not exist: {current}"


def test_default_wide_caps_template_builds_stepped_layout_without_override():
    layout = REPO_ROOT / "kle-jsons" / "test_stepped-capslock.json"
    model = build_model(layout, stepped_key="wide-caps")

    assert fpg.KIND_WIDE_CAPS in model.kinds
    assert model.templates["wide-caps"].path == (
        REPO_ROOT / fpg.DEFAULT_SOCKET_WIDE_CAPS
    )
