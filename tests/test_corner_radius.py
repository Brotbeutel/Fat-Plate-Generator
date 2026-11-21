import math

import pytest
from shapely.geometry import Polygon

import fat_plate_generator as fpg
from tests.conftest import build_model


def test_square_rounding_uses_the_formula():
    a = 20.0
    radius = 3.0
    square = Polygon([(0, 0), (a, 0), (a, a), (0, a)])
    rounded = fpg.round_shapely_polygon(square, radius)
    expected = a * a - (4 - math.pi) * radius * radius
    assert abs(rounded.area - expected) < 0.001


def test_l_shape_rounding_uses_the_formula():
    l_shape = Polygon([(0, 0), (12, 0), (12, 6), (6, 6),
                       (6, 12), (0, 12)])
    radius = 1.5
    rounded = fpg.round_shapely_polygon(l_shape, radius)
    expected = l_shape.area - (4 - math.pi) * radius * radius
    assert abs(rounded.area - expected) < 0.001


def test_60_degree_tangent_length_and_closed_segments():
    ring = [(0, 0), (10, 0), (5, 10 * math.tan(math.pi / 3))]
    radius = 2.0
    segments, truncated, minimum = fpg.rounded_ring_segments(ring, radius)
    arcs = [segment for segment in segments if segment["type"] == "arc"]
    assert truncated == 0
    assert minimum == radius
    assert arcs
    assert abs(arcs[0]["start"][0] - 0.0) < 1e-9 or len(arcs) > 0
    assert segments[-1]["end"] == segments[0]["start"]


def test_short_edge_trims_both_sides_and_reports_warning():
    ring = [(0, 0), (5, 0), (5, 5), (0, 5)]
    segments, truncated, minimum = fpg.rounded_ring_segments(ring, 3.0)
    assert truncated == 4
    assert 0 < minimum < 3.0
    assert all(segment["type"] in {"line", "arc"} for segment in segments)


def test_radius_zero_returns_the_original_ring():
    ring = [(0, 0), (10, 0), (10, 10), (0, 10)]
    segments, truncated, minimum = fpg.rounded_ring_segments(ring, 0.0)
    assert truncated == 0
    assert minimum == 0.0
    assert all(segment["type"] == "line" for segment in segments)


@pytest.fixture
def one_key_layout(tmp_path):
    path = tmp_path / "one-key.json"
    path.write_text('[["Q"]]', encoding="utf-8")
    return path


def test_one_key_volume_and_validity(one_key_layout):
    plain = build_model(one_key_layout, single_mesh=False, corner_radius=0.0)
    rounded = build_model(one_key_layout, single_mesh=False, corner_radius=3.0)
    thickness = fpg.PLATE_Z_MAX - fpg.PLATE_Z_MIN
    expected = (4 - math.pi) * 3.0 ** 2 * thickness
    measured = plain.plate.Volume() - rounded.plate.Volume()
    assert abs(measured - expected) / expected < 1e-6
    assert rounded.plate.isValid()
    assert abs(sum(cavity.Volume() for cavity in plain.cavities)
               - sum(cavity.Volume() for cavity in rounded.cavities)) < 1e-9
    assert rounded.footprint.bounds[0] == 0.0
    assert rounded.footprint.bounds[1] == 0.0


def test_iso_enter_volume_uses_the_right_angle_formula(tmp_path):
    layout = tmp_path / "iso-enter.json"
    layout.write_text(
        '[[{"w":1.25,"h":2,"w2":1.5,"h2":1,"x2":-0.25},"Enter"]]',
        encoding="utf-8",
    )
    plain = build_model(layout, single_mesh=False, corner_radius=0.0)
    rounded = build_model(layout, single_mesh=False, corner_radius=1.5)
    thickness = fpg.PLATE_Z_MAX - fpg.PLATE_Z_MIN
    expected = (4 - math.pi) * 1.5 ** 2 * thickness
    measured = plain.plate.Volume() - rounded.plate.Volume()
    assert abs(measured - expected) / expected < 1e-6


def test_g80_1800_small_margin_and_corner_radius_remain_valid():
    layout = (fpg.SCRIPT_DIR / "kle-jsons"
              / "keyboard-layout_100-percent-iso-105-keys_g80-1800_stepped-capslock.json")
    settings = fpg.Settings(
        margin=9.262315,
        corner_radius=2.0,
        stepped_key="wide-caps",
        fuse_f_row=True,
        single_mesh=False,
        spacebar_position="off-centered-right",
    )
    model = fpg.build_plate_model(layout, settings)
    assert model.plate.isValid()
    assert model.footprint.is_valid
    assert len(fpg.polygons(model.footprint)) == 2


def test_config_and_settings_corner_radius(tmp_path, one_key_layout):
    assert fpg.Settings().corner_radius == 0.0
    assert fpg.Settings(corner_radius=3.0).corner_radius == 3.0
    with pytest.raises(ValueError, match="corner_radius"):
        fpg.Settings(corner_radius=-1)
    with pytest.raises(ValueError, match="corner_radius"):
        fpg.Settings(corner_radius=float("inf"))

    config = tmp_path / "corners.toml"
    config.write_text("corner_radius = 2.5\n", encoding="utf-8")
    assert fpg.load_config(config).corner_radius == 2.5

    invalid = tmp_path / "invalid.toml"
    invalid.write_text('corner_radius = "wide"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="corner_radius"):
        fpg.load_config(invalid)

    parser = fpg.build_parser()
    default_args = parser.parse_args(["--json", str(one_key_layout)])
    assert fpg.settings_from_args(default_args).corner_radius == 0.0
    config_args = parser.parse_args(["--config", str(config), "--json", str(one_key_layout)])
    assert fpg.settings_from_args(config_args).corner_radius == 2.5
    cli_args = parser.parse_args([
        "--config", str(config), "--json", str(one_key_layout), "--corner-radius", "4",
    ])
    assert fpg.settings_from_args(cli_args).corner_radius == 4.0

