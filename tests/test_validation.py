"""validate_exported_stl(): synthetic meshes, independent of the template STLs."""
from __future__ import annotations

import numpy as np
import pytest
import trimesh

import fat_plate_generator as fpg


def write_box(path, extents=(10.0, 20.0, 5.0)):
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(-mesh.bounds[0])          # corner at the origin
    mesh.export(path)
    return mesh


def test_accepts_a_closed_box(tmp_path, capsys):
    path = tmp_path / "box.stl"
    write_box(path)
    mesh = fpg.validate_exported_stl(path)
    assert mesh.is_watertight and mesh.volume == pytest.approx(1000.0)
    assert "STL validation passed" in capsys.readouterr().out


def test_accepts_matching_bounds(tmp_path):
    path = tmp_path / "box.stl"
    write_box(path)
    fpg.validate_exported_stl(path, expected_bounds=((0, 0, 0), (10, 20, 5)))


def test_rejects_bounds_that_differ(tmp_path):
    path = tmp_path / "box.stl"
    write_box(path)
    with pytest.raises(RuntimeError, match="bounds differ"):
        fpg.validate_exported_stl(path, expected_bounds=((0, 0, 0), (10, 20, 6)))


def test_bounds_tolerance_is_respected(tmp_path):
    path = tmp_path / "box.stl"
    write_box(path)
    fpg.validate_exported_stl(path, expected_bounds=((0, 0, 0), (10.05, 20, 5)), bounds_tolerance=0.1)
    with pytest.raises(RuntimeError):
        fpg.validate_exported_stl(path, expected_bounds=((0, 0, 0), (10.05, 20, 5)), bounds_tolerance=0.01)


@pytest.mark.parametrize("bad", [((0, 0), (1, 1)), ((0, 0, 0), (np.nan, 1, 1)), ((2, 0, 0), (1, 1, 1))])
def test_rejects_malformed_expected_bounds(tmp_path, bad):
    path = tmp_path / "box.stl"
    write_box(path)
    with pytest.raises(ValueError):
        fpg.validate_exported_stl(path, expected_bounds=bad)


def test_rejects_a_missing_file(tmp_path):
    with pytest.raises(RuntimeError, match="was not created"):
        fpg.validate_exported_stl(tmp_path / "missing.stl")


def test_rejects_an_empty_file(tmp_path):
    path = tmp_path / "empty.stl"
    path.write_bytes(b"")
    with pytest.raises(RuntimeError, match="empty"):
        fpg.validate_exported_stl(path)


def test_rejects_an_open_mesh(tmp_path):
    path = tmp_path / "open.stl"
    mesh = trimesh.creation.box(extents=(10, 20, 5))
    mesh.update_faces(np.arange(len(mesh.faces)) != 0)       # drop one triangle
    mesh.export(path)
    with pytest.raises(RuntimeError, match="not watertight"):
        fpg.validate_exported_stl(path)


def test_rejects_inside_out_faces(tmp_path):
    path = tmp_path / "inverted.stl"
    mesh = trimesh.creation.box(extents=(10, 20, 5))
    mesh.invert()
    mesh.export(path)
    with pytest.raises(RuntimeError, match="outward-facing"):
        fpg.validate_exported_stl(path)


def test_does_not_touch_the_file(tmp_path):
    path = tmp_path / "box.stl"
    write_box(path)
    before = path.read_bytes()
    fpg.validate_exported_stl(path)
    assert path.read_bytes() == before
