"""Config file (TOML): format, precedence, errors, paths, CLI and preview.

Most tests need no CAD: they go through ``build_parser()`` and
``settings_from_args()``.  The end-to-end tests run the generator as a
subprocess on the small orientation layout.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

import fat_plate_generator as fpg
from tests.conftest import ORIENTATION_LAYOUT, REPO_ROOT
from tools import preview

EXAMPLE_CONFIG = REPO_ROOT / "fat_plate_config.example.toml"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def write_config(folder: Path, text: str, name: str = "cfg.toml") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")                  # only the existence of a template is checked at load time
    return path


def settings(*argv) -> fpg.Settings:
    return fpg.settings_from_args(fpg.build_parser().parse_args([str(a) for a in argv]))


def toml_path(path: Path) -> str:
    return path.as_posix()                 # forward slashes are valid in a TOML string on Windows too


# --------------------------------------------------------------------------
# defaults and the example file
# --------------------------------------------------------------------------
def test_without_config_and_options_the_settings_are_the_defaults():
    assert settings() == fpg.Settings()


def test_help_names_real_defaults_not_none():
    assert "None" not in fpg.build_parser().format_help()


def test_example_config_gives_the_default_settings():
    assert fpg.load_config(EXAMPLE_CONFIG) == fpg.Settings()


def test_example_config_lists_every_key():
    """If a key is added to the loader, the example has to show it."""
    tomllib = pytest.importorskip("tomllib")
    raw = tomllib.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    assert set(raw) == set(fpg.CONFIG_KEYS) | set(fpg.CONFIG_TABLES)
    for table, keys in fpg.CONFIG_TABLES.items():
        assert set(raw[table]) == set(keys)


def test_an_empty_config_changes_nothing(tmp_path):
    assert settings("--config", write_config(tmp_path, "")) == fpg.Settings()


# --------------------------------------------------------------------------
# precedence: command line > config file > built-in default
# --------------------------------------------------------------------------
def test_precedence_of_a_number(tmp_path):
    config = write_config(tmp_path, "margin = 2.5\n")
    assert settings().margin == 1.0
    assert settings("--config", config).margin == 2.5
    assert settings("--config", config, "--margin", 4).margin == 4.0


def test_precedence_of_a_choice(tmp_path):
    config = write_config(tmp_path, 'spacebar_position = "off-centered-left"\n'
                                    '[orientation]\nstab_rotation_vertical = 270\n')
    assert settings().spacebar_position == "centered"
    assert settings("--config", config).spacebar_position == "off-centered-left"
    result = settings("--config", config, "--spacebar-position", "off-centered-right",
                      "--stab-rotation-vertical", 0)
    assert result.spacebar_position == "off-centered-right"
    assert result.orientation.stab_rotation_vertical == 0
    # an option that was not given leaves the config value alone
    assert settings("--config", config, "--stab-rotation-horizontal", 0
                    ).orientation.stab_rotation_vertical == 270


def test_precedence_of_a_path(tmp_path):
    socket = touch(tmp_path / "from_config.stl")
    config = write_config(tmp_path, f'[templates]\nsocket = "{toml_path(socket)}"\n')
    default = fpg.Settings().templates
    assert settings().templates.socket == default.socket
    assert settings("--config", config).templates.socket == socket
    assert settings("--config", config, "--socket", "from_cli.stl").templates.socket == Path("from_cli.stl")
    # the other templates keep their defaults
    assert settings("--config", config).templates.stabilizer_2u == default.stabilizer_2u


def test_precedence_of_stabilizer_3u_path(tmp_path):
    stab = touch(tmp_path / "my_3u.stl")
    config = write_config(tmp_path, f'[templates]\nstabilizer_3u = "{toml_path(stab)}"\n')
    default = fpg.Settings().templates
    assert settings().templates.stabilizer_3u == default.stabilizer_3u
    assert settings("--config", config).templates.stabilizer_3u == stab
    assert settings("--config", config, "--stabilizer-3u", "cli_3u.stl").templates.stabilizer_3u == Path("cli_3u.stl")


def test_precedence_of_a_switch(tmp_path):
    config = write_config(tmp_path, "single_mesh = true\n")
    assert settings().single_mesh is False
    assert settings("--single-mesh").single_mesh is True
    assert settings("--config", config).single_mesh is True
    assert settings("--config", config, "--single-mesh").single_mesh is True
    assert settings("--config", config, "--no-single-mesh").single_mesh is False


def test_precedence_of_the_fuse_f_row_switch(tmp_path):
    config = write_config(tmp_path, "fuse_f_row = true\n")
    assert settings().fuse_f_row is False
    assert settings("--fuse-f-row").fuse_f_row is True
    assert settings("--config", config).fuse_f_row is True
    assert settings("--config", config, "--fuse-f-row").fuse_f_row is True
    assert settings("--config", config, "--no-fuse-f-row").fuse_f_row is False
    # the switch is independent of single_mesh: both can be set
    both = settings("--config", config, "--single-mesh")
    assert (both.fuse_f_row, both.single_mesh) == (True, True)


def test_a_config_with_fuse_f_row_false_keeps_the_default(tmp_path):
    config = write_config(tmp_path, "fuse_f_row = false\n")
    assert settings("--config", config) == fpg.Settings()
    assert settings("--config", config, "--fuse-f-row").fuse_f_row is True


def test_fuse_f_row_must_be_a_boolean_in_settings():
    for value in ("yes", 1, None):
        with pytest.raises(ValueError, match="fuse_f_row must be a boolean"):
            fpg.Settings(fuse_f_row=value)


def test_orientation_switches_and_the_new_options(tmp_path):
    config = write_config(tmp_path, "[orientation]\nglobal_rotation = 90\nglobal_mirror_x = true\n")
    assert settings().orientation.global_rotation == 0
    assert settings().orientation.global_mirror_x is False
    assert settings("--global-rotation", 270).orientation.global_rotation == 270
    from_config = settings("--config", config).orientation
    assert (from_config.global_rotation, from_config.global_mirror_x) == (90, True)
    from_cli = settings("--config", config, "--global-rotation", 0, "--no-global-mirror-x").orientation
    assert (from_cli.global_rotation, from_cli.global_mirror_x) == (0, False)
    assert settings("--global-mirror-x").orientation.global_mirror_x is True


def test_stab_mirror_switches_and_the_usual_precedence(tmp_path):
    horizontal_on = write_config(tmp_path, "[orientation]\nstab_mirror_horizontal = true\n", "h.toml")
    vertical_off = write_config(tmp_path, "[orientation]\nstab_mirror_vertical = false\n", "v.toml")
    # default: both off
    default = settings().orientation
    assert (default.stab_mirror_horizontal, default.stab_mirror_vertical) == (False, False)
    # config beats the default; a key that is not given leaves the default alone
    from_config = settings("--config", horizontal_on).orientation
    assert (from_config.stab_mirror_horizontal, from_config.stab_mirror_vertical) == (True, False)
    # command line beats the config, in both forms, for each switch
    cli = settings("--config", horizontal_on, "--no-stab-mirror-horizontal", "--stab-mirror-vertical").orientation
    assert (cli.stab_mirror_horizontal, cli.stab_mirror_vertical) == (False, True)
    assert settings("--config", vertical_off, "--stab-mirror-vertical").orientation.stab_mirror_vertical is True
    assert settings("--stab-mirror-horizontal").orientation.stab_mirror_horizontal is True
    # an option that was not given leaves the config value alone
    assert settings("--config", horizontal_on, "--stab-mirror-vertical"
                    ).orientation.stab_mirror_horizontal is True


def test_global_transform_has_both_forms_and_the_usual_precedence(tmp_path):
    off = write_config(tmp_path, "[orientation]\nglobal_transform = false\n", "off.toml")
    on = write_config(tmp_path, "[orientation]\nglobal_transform = true\n", "on.toml")
    # without a config: the default is on; the old form still switches it off
    assert settings().orientation.global_transform is True
    assert settings("--global-transform").orientation.global_transform is True
    assert settings("--no-global-transform").orientation.global_transform is False
    # the config is used when no option is given
    assert settings("--config", off).orientation.global_transform is False
    assert settings("--config", on).orientation.global_transform is True
    # the command line wins in both directions
    assert settings("--config", off, "--global-transform").orientation.global_transform is True
    assert settings("--config", on, "--no-global-transform").orientation.global_transform is False


# --------------------------------------------------------------------------
# errors: file name, key and what is expected
# --------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("marign = 1.0\n", "cfg.toml: unknown key 'marign'"),
    ("[orientation]\nstab_rotation_vertcal = 90\n", "cfg.toml: unknown key 'orientation.stab_rotation_vertcal'"),
    ("[templates]\nsocked = \"x.stl\"\n", "cfg.toml: unknown key 'templates.socked'"),
    ("[orienation]\nglobal_rotation = 90\n", "cfg.toml: unknown key 'orienation'"),
    ("[templates]\nspacebar_off_centered_left = \"x.stl\"\n",
     "cfg.toml: unknown key 'templates.spacebar_off_centered_left'"),
    ("[templates]\nspacebar_off_centered_right = \"x.stl\"\n",
     "cfg.toml: unknown key 'templates.spacebar_off_centered_right'"),
    ('margin = "1"\n', "cfg.toml: 'margin' must be a number, got '1' (str)"),
    ("margin = true\n", "cfg.toml: 'margin' must be a number"),
    ("stabilizer_min_unit = 'two'\n", "'stabilizer_min_unit' must be a number"),
    ('single_mesh = "yes"\n', "'single_mesh' must be true or false"),
    ('fuse_f_row = "yes"\n', "cfg.toml: 'fuse_f_row' must be true or false, got 'yes' (str)"),
    ("fuse_f_row = 1\n", "cfg.toml: 'fuse_f_row' must be true or false, got 1 (int)"),
    ("spacebar_position = 3\n", "'spacebar_position' must be a string"),
    ("[orientation]\nstab_rotation_vertical = 90.0\n", "'orientation.stab_rotation_vertical' must be an integer"),
    ("[orientation]\nglobal_mirror_x = 1\n", "'orientation.global_mirror_x' must be true or false"),
    ("[orientation]\nstab_mirror_horizontal = 1\n",
     "cfg.toml: 'orientation.stab_mirror_horizontal' must be true or false, got 1 (int)"),
    ('[orientation]\nstab_mirror_vertical = "yes"\n',
     "cfg.toml: 'orientation.stab_mirror_vertical' must be true or false, got 'yes' (str)"),
    ("[templates]\nsocket = 5\n", "'templates.socket' must be a path"),
    ("orientation = 3\n", "'orientation' must be a table"),
    ("[orientation]\nstab_rotation_vertical = 45\n",
     "cfg.toml: stab_rotation_vertical must be one of (0, 90, 180, 270), got 45"),
    ("margin = -1.0\n", "cfg.toml: margin must be a non-negative number"),
    ("stabilizer_min_unit = 0\n", "cfg.toml: stabilizer_min_unit must be a positive number"),
    ('spacebar_position = "left"\n', "cfg.toml: spacebar_position must be one of"),
    ('stepped_key = "wide"\n', "cfg.toml: stepped_key must be one of"),
])
def test_invalid_config_is_refused_with_file_key_and_expectation(tmp_path, text, expected):
    with pytest.raises(ValueError) as error:
        fpg.load_config(write_config(tmp_path, text))
    assert expected in str(error.value)


def test_a_missing_template_file_is_refused(tmp_path):
    config = write_config(tmp_path, '[templates]\nstabilizer_2u = "nowhere/stabilizer_2-00u.stl"\n')
    with pytest.raises(ValueError) as error:
        fpg.load_config(config)
    message = str(error.value)
    assert "cfg.toml" in message and "templates.stabilizer_2u" in message and "stabilizer_2-00u.stl" in message
    assert "not found" in message


def test_a_missing_stabilizer_3u_file_is_refused(tmp_path):
    config = write_config(tmp_path, '[templates]\nstabilizer_3u = "nowhere/stabilizer_3-00u.stl"\n')
    with pytest.raises(ValueError) as error:
        fpg.load_config(config)
    message = str(error.value)
    assert "cfg.toml" in message and "templates.stabilizer_3u" in message and "stabilizer_3-00u.stl" in message
    assert "not found" in message


def test_a_missing_config_file_is_refused(tmp_path):
    with pytest.raises(ValueError, match="config file not found"):
        settings("--config", tmp_path / "nicht_da.toml")


def test_broken_toml_is_refused(tmp_path):
    with pytest.raises(ValueError, match=r"cfg\.toml: not a valid TOML file"):
        fpg.load_config(write_config(tmp_path, "margin = \n"))


def test_python_without_tomllib_gives_a_clear_message(tmp_path, monkeypatch):
    config = write_config(tmp_path, "margin = 2.0\n")
    monkeypatch.setitem(sys.modules, "tomllib", None)          # makes "import tomllib" fail
    with pytest.raises(ValueError, match="config files need Python 3.11 or newer"):
        settings("--config", config)
    assert settings() == fpg.Settings()                         # without --config it is not needed


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------
def test_relative_template_paths_are_relative_to_the_config_folder(tmp_path, monkeypatch):
    socket = touch(tmp_path / "conf" / "templates" / "my_socket.stl")
    write_config(tmp_path / "conf", '[templates]\nsocket = "templates/my_socket.stl"\n')
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)                    # not the config folder, not the repository
    result = settings("--config", Path("..") / "conf" / "cfg.toml")
    assert result.templates.socket == socket.resolve()


def test_absolute_template_paths_stay_as_they_are(tmp_path):
    socket = touch(tmp_path / "somewhere" / "s.stl")
    config = write_config(tmp_path / "conf", f'[templates]\nsocket = "{toml_path(socket)}"\n')
    assert settings("--config", config).templates.socket == socket


def test_command_line_paths_stay_relative_to_the_working_folder(tmp_path):
    config = write_config(tmp_path, "margin = 2.0\n")
    assert settings("--config", config, "--stabilizer-2u", "sub/stab.stl").templates.stabilizer_2u == Path("sub/stab.stl")


# --------------------------------------------------------------------------
# command line: the first line of an error is readable
# --------------------------------------------------------------------------
def run_generator(*args, cwd=REPO_ROOT):
    return subprocess.run([sys.executable, str(REPO_ROOT / "fat_plate_generator.py"), *args],
                          capture_output=True, text=True, cwd=cwd)


@pytest.mark.parametrize("config_text, expected", [
    (None, "ERROR: config file not found"),
    ("marign = 1.0\n", "ERROR: cfg.toml: unknown key 'marign'"),
])
def test_cli_config_errors_start_with_a_readable_error_line(tmp_path, config_text, expected):
    config = tmp_path / "nicht_da.toml" if config_text is None else write_config(tmp_path, config_text)
    result = run_generator("--json", str(ORIENTATION_LAYOUT), "--config", str(config),
                           "--output", str(tmp_path / "x.stl"))
    assert result.returncode != 0
    lines = result.stderr.splitlines()
    error_line = next(i for i, line in enumerate(lines) if line.startswith("ERROR:"))
    assert lines[error_line].startswith(expected), lines[error_line]
    assert all("Traceback" not in line for line in lines[:error_line])   # the message comes first
    assert not (tmp_path / "x.stl").exists()


# --------------------------------------------------------------------------
# end to end: a config gives the same plate as the equivalent options
# --------------------------------------------------------------------------
def mesh_summary(path):
    mesh = trimesh.load(path, force="mesh")
    return len(mesh.faces), float(mesh.volume), np.asarray(mesh.bounds)


def assert_same_plate(a, b):
    faces_a, volume_a, bounds_a = mesh_summary(a)
    faces_b, volume_b, bounds_b = mesh_summary(b)
    assert faces_a == faces_b
    assert volume_a == pytest.approx(volume_b, rel=1e-9)
    assert np.allclose(bounds_a, bounds_b, atol=1e-9)


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """The same layout generated four ways (each run takes a while, so once per module)."""
    folder = tmp_path_factory.mktemp("config_runs")
    layout = str(ORIENTATION_LAYOUT)
    custom = write_config(folder, "margin = 2.0\n[orientation]\nstab_rotation_horizontal = 180\n", "custom.toml")
    jobs = {
        "plain": [],
        "example": ["--config", str(EXAMPLE_CONFIG)],
        "config": ["--config", str(custom)],
        "options": ["--margin", "2", "--stab-rotation-horizontal", "180"],
    }
    results = {}
    for name, extra in jobs.items():
        out = folder / f"{name}.stl"
        run = run_generator("--json", layout, "--output", str(out), *extra)
        assert run.returncode == 0, run.stderr
        results[name] = (out, run)
    results["custom_config"] = custom
    return results


def test_the_example_config_gives_the_same_plate_as_no_config(runs):
    assert_same_plate(runs["example"][0], runs["plain"][0])


def test_a_config_gives_the_same_plate_as_the_equivalent_options(runs):
    assert_same_plate(runs["config"][0], runs["options"][0])


def test_the_config_really_changed_the_plate(runs):
    """Guards against a config that is read but ignored."""
    plain, config = mesh_summary(runs["plain"][0]), mesh_summary(runs["config"][0])
    assert config[2][1][0] - config[2][0][0] > plain[2][1][0] - plain[2][0][0]      # wider margin
    assert "horizontal 180 deg" in runs["config"][1].stdout      # an offset; the default is 0
    assert "horizontal 0 deg" in runs["plain"][1].stdout


def test_the_header_names_the_config(runs):
    assert f"Config:          {EXAMPLE_CONFIG}" in runs["example"][1].stdout
    assert f"Config:          {runs['custom_config']}" in runs["config"][1].stdout
    assert "Config:          none" in runs["plain"][1].stdout
    assert "Config:          none" in runs["options"][1].stdout


# --------------------------------------------------------------------------
# preview tool
# --------------------------------------------------------------------------
def test_preview_without_config_is_unchanged():
    margin, matrix, transform = preview.plate_options()
    assert (margin, matrix, transform) == (fpg.DEFAULT_MARGIN, preview.GLOBAL_MATRIX, True)
    assert preview.plate_options(no_global_transform=True) == (fpg.DEFAULT_MARGIN, fpg.IDENTITY_MATRIX, False)


def test_preview_reads_margin_and_transform_from_the_config(tmp_path):
    config = write_config(tmp_path, "margin = 2.5\n[orientation]\nglobal_rotation = 90\n")
    margin, matrix, transform = preview.plate_options(config)
    assert margin == 2.5 and transform is True
    assert matrix == fpg.global_matrix(fpg.OrientationConfig(global_rotation=90)) == (0, 1, 1, 0)


def test_preview_command_line_wins_over_the_config(tmp_path):
    config = write_config(tmp_path, "margin = 2.5\n[orientation]\nglobal_rotation = 90\n")
    assert preview.plate_options(config, margin=3.0)[0] == 3.0
    assert preview.plate_options(config, no_global_transform=True) == (2.5, fpg.IDENTITY_MATRIX, False)
    switched_off = write_config(tmp_path, "[orientation]\nglobal_transform = false\n", "off.toml")
    assert preview.plate_options(switched_off) == (fpg.DEFAULT_MARGIN, fpg.IDENTITY_MATRIX, False)


def test_preview_with_a_config_places_the_keys_like_the_generator(tmp_path):
    """The placement under a config with another rotation matches what the generator
    computes for the same settings (footprint shifted to the origin, centres shifted)."""
    config = write_config(tmp_path, "margin = 2.5\n[orientation]\nglobal_rotation = 90\n")
    margin, matrix, _ = preview.plate_options(config)
    keys = fpg.parse_kle(json.loads(ORIENTATION_LAYOUT.read_text(encoding="utf-8")))
    footprint = fpg.plate_footprint(keys, matrix, margin)
    minx, miny, maxx, maxy = footprint.bounds
    expected = [tuple(c - o for c, o in zip(fpg.apply_matrix(matrix, *fpg.switch_center(k)), (minx, miny)))
                for k in keys]
    placed = preview.keys_in_plate_frame(keys, np.array([[0, 0, 0], [maxx - minx, maxy - miny, 0]]),
                                         margin, matrix)
    for p, center in zip(placed, expected):
        assert p["center"] == pytest.approx(center, abs=1e-6)
    # and it differs from the default placement
    default_matrix = preview.plate_options()[1]
    default = preview.keys_in_plate_frame(keys, np.array([[0, 0, 0], [maxx - minx, maxy - miny, 0]]),
                                          fpg.DEFAULT_MARGIN, default_matrix)
    assert [p["center"] for p in placed] != [p["center"] for p in default]


def test_preview_refuses_a_broken_config(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["preview.py", str(tmp_path / "plate.stl"), "--layout",
                                      str(ORIENTATION_LAYOUT), "--config", str(tmp_path / "nicht_da.toml")])
    with pytest.raises(SystemExit) as exit_info:
        preview.main()
    assert exit_info.value.code == 2
    assert "config file not found" in capsys.readouterr().err


def test_preview_renders_with_a_config(runs, tmp_path):
    margin, matrix, transform = preview.plate_options(runs["custom_config"])
    png = preview.render_preview(runs["config"][0], ORIENTATION_LAYOUT, tmp_path / "preview.png",
                                 margin=margin, global_transform=transform, matrix=matrix, dpi=40)
    assert png.is_file() and png.stat().st_size > 0
