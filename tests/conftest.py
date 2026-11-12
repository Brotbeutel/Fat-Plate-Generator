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


def build_model(layout: Path, **kwargs):
    """build_plate_model() with the repository's template STLs."""
    templates = kwargs.pop("templates", None)
    if templates is None:
        templates = fpg.TemplateSet.defaults(REPO_ROOT)

    tmpl_kwargs = {}
    for name in ("socket", "wide_caps", "stabilizer_2u", "stabilizer_3u",
                 "spacebar_6u_centered", "spacebar_6u_off_centered",
                 "spacebar_6_25u_centered", "spacebar_6_25u_off_centered",
                 "spacebar_7u_centered"):
        if name in kwargs:
            tmpl_kwargs[name] = kwargs.pop(name)
    if tmpl_kwargs:
        templates = templates.replace(**tmpl_kwargs)

    settings = kwargs.pop("settings", None)
    if settings is None:
        settings = fpg.Settings(templates=templates, **kwargs)
    return fpg.build_plate_model(layout, settings)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def orientation_model():
    return build_model(ORIENTATION_LAYOUT)


@pytest.fixture(scope="session")
def full_model():
    return build_model(FULL_LAYOUT)
