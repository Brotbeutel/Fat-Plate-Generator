"""check_exported_stl(): synthetic meshes, independent of the template STLs."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

import fat_plate_generator as fpg


def write_box(path, extents=(10.0, 20.0, 5.0)):
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(-mesh.bounds[0])          # corner at the origin
    mesh.export(path)
    return mesh


def test_accepts_a_closed_box(tmp_path):
    path = tmp_path / "box.stl"
    write_box(path)
    mesh, problems = fpg.check_exported_stl(path)
    assert problems == []
    assert mesh.is_watertight and mesh.volume == pytest.approx(1000.0)


def test_accepts_matching_bounds(tmp_path):
    path = tmp_path / "box.stl"
    write_box(path)
    _, problems = fpg.check_exported_stl(path, expected_bounds=((0, 0, 0), (10, 20, 5)))
    assert problems == []


def test_reports_bounds_that_differ(tmp_path):
    path = tmp_path / "box.stl"
    write_box(path)
    _, problems = fpg.check_exported_stl(path, expected_bounds=((0, 0, 0), (10, 20, 6)))
    assert len(problems) == 1 and "bounds differ" in problems[0]


def test_bounds_tolerance_is_respected(tmp_path):
    path = tmp_path / "box.stl"
    write_box(path)
    expected = ((0, 0, 0), (10.05, 20, 5))
    assert fpg.check_exported_stl(path, expected_bounds=expected, bounds_tolerance=0.1)[1] == []
    assert fpg.check_exported_stl(path, expected_bounds=expected, bounds_tolerance=0.01)[1]


@pytest.mark.parametrize("bad", [((0, 0), (1, 1)), ((0, 0, 0), (np.nan, 1, 1)), ((2, 0, 0), (1, 1, 1))])
def test_rejects_malformed_expected_bounds(tmp_path, bad):
    path = tmp_path / "box.stl"
    write_box(path)
    with pytest.raises(ValueError):
        fpg.check_exported_stl(path, expected_bounds=bad)


def test_rejects_a_missing_file(tmp_path):
    with pytest.raises(RuntimeError, match="was not created"):
        fpg.check_exported_stl(tmp_path / "missing.stl")


def test_rejects_an_empty_file(tmp_path):
    path = tmp_path / "empty.stl"
    path.write_bytes(b"")
    with pytest.raises(RuntimeError, match="empty"):
        fpg.check_exported_stl(path)


def test_reports_an_open_mesh_with_edge_counts(tmp_path):
    path = tmp_path / "open.stl"
    mesh = trimesh.creation.box(extents=(10, 20, 5))
    mesh.update_faces(np.arange(len(mesh.faces)) != 0)       # drop one triangle
    mesh.export(path)
    _, problems = fpg.check_exported_stl(path)
    assert any("not watertight" in p and "3 open edges" in p for p in problems), problems


def test_reports_inside_out_faces(tmp_path):
    path = tmp_path / "inverted.stl"
    mesh = trimesh.creation.box(extents=(10, 20, 5))
    mesh.invert()
    mesh.export(path)
    _, problems = fpg.check_exported_stl(path)
    assert any("outward-facing" in p for p in problems), problems


def test_does_not_touch_the_file(tmp_path):
    path = tmp_path / "box.stl"
    write_box(path)
    before = path.read_bytes()
    fpg.check_exported_stl(path)
    assert path.read_bytes() == before


def test_report_is_quiet_on_stdout_when_clean(tmp_path, capsys):
    path = tmp_path / "box.stl"
    write_box(path)
    mesh, problems = fpg.check_exported_stl(path)
    fpg.report_stl_check(mesh, problems, path)
    out = capsys.readouterr()
    assert "STL check:       passed" in out.out and out.err == ""


def test_report_warns_explicitly_on_problems(tmp_path, capsys):
    path = tmp_path / "x.stl"
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    fpg.report_stl_check(mesh, ["not watertight: 3 open edges"], path)
    out = capsys.readouterr()
    assert "WARNING" in out.err and "not watertight: 3 open edges" in out.err
    assert str(path) in out.err and out.out == ""


def test_generate_warns_but_still_succeeds(tmp_path, monkeypatch, capsys):
    """A mesh problem must never abort the run: the STL is written, a warning is printed."""
    monkeypatch.setattr(fpg, "check_exported_stl",
                        lambda *a, **k: (trimesh.creation.box(), ["not watertight: test"]))
    root = Path(fpg.__file__).parent
    out = tmp_path / "plate.stl"
    fpg.generate(root / "tests" / "layouts" / "stabilizer_orientation.json",
                 root / fpg.DEFAULT_SOCKET, root / fpg.DEFAULT_STABILIZER,
                 root / fpg.DEFAULT_SPACEBAR_CENTERED, root / fpg.DEFAULT_SPACEBAR_OFF_CENTERED,
                 output=out)
    captured = capsys.readouterr()
    assert out.exists() and out.stat().st_size > 0
    assert "WARNING" in captured.err and "Done, with warnings." in captured.out
