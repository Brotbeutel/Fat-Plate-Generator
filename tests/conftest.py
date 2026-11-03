"""Shared fixtures for the Fat Plate Generator tests.

Building the 100% layout takes about half a minute, so models are built once
per test session.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import fat_plate_generator as fpg  # noqa: E402

ORIENTATION_LAYOUT = REPO_ROOT / "tests" / "layouts" / "stabilizer_orientation.json"
FULL_LAYOUT = REPO_ROOT / fpg.DEFAULT_JSON


def spacebar_paths(root: Path = REPO_ROOT) -> dict:
    """The spacebar templates of the repository, by switch position."""
    return {"centered": root / fpg.DEFAULT_SPACEBAR_CENTERED,
            "off-centered-left": root / fpg.DEFAULT_SPACEBAR_OFF_CENTERED_LEFT,
            "off-centered-right": root / fpg.DEFAULT_SPACEBAR_OFF_CENTERED_RIGHT}


def build_model(layout: Path, **kwargs):
    """build_plate_model() with the repository's template STLs."""
    return fpg.build_plate_model(
        layout,
        REPO_ROOT / fpg.DEFAULT_SOCKET,
        REPO_ROOT / fpg.DEFAULT_STABILIZER,
        spacebar_paths(),
        **kwargs)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def orientation_model():
    return build_model(ORIENTATION_LAYOUT)


@pytest.fixture(scope="session")
def full_model():
    return build_model(FULL_LAYOUT)
