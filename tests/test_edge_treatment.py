import math

import pytest
from shapely.affinity import scale
from shapely.geometry import Polygon

import fat_plate_generator as fpg
from tests.conftest import REPO_ROOT, build_model


def polygon_area_by_form(poly, radius, size, kind):
    if kind == "fillet":
        cross_section = size * size * (1 - math.pi / 4)
        centre_offset = size * (5 / 6 - math.pi / 4) / (1 - math.pi / 4)
    else:
        cross_section = size * size / 2
        centre_offset = size / 3

    coords = list(poly.exterior.coords)
    straight = 0.0
    convex = 0.0
    concave = 0.0
    for i, vertex in enumerate(coords[:-1]):
        prev = coords[i - 1]
        nxt = coords[(i + 1) % (len(coords) - 1)]
        v1 = (vertex[0] - prev[0], vertex[1] - prev[1])
        v2 = (nxt[0] - vertex[0], nxt[1] - vertex[1])
        l1 = math.hypot(*v1)
        l2 = math.hypot(*v2)
        if l1 == 0 or l2 == 0:
            continue
        u1 = (v1[0] / l1, v1[1] / l1)
        u2 = (v2[0] / l2, v2[1] / l2)
        turn = u1[0] * u2[1] - u1[1] * u2[0]
        dot = u1[0] * u2[0] + u1[1] * u2[1]
        angle = math.atan2(turn, dot)
        if abs(angle) <= 1e-9:
            straight += math.hypot(nxt[0] - vertex[0], nxt[1] - vertex[1])
        elif angle > 0:
            convex += abs(angle)
        else:
            concave += abs(angle)
    effective_length = (straight
                        + sum(convex * (radius - centre_offset)
                              for _ in (0,))
                        + sum(concave * (radius + centre_offset)
                              for _ in (0,))
                        if radius > 0 else straight)
    return 2 * cross_section * effective_length


@pytest.fixture
def one_key_layout(tmp_path):
    path = tmp_path / "one-key-edge.json"
    path.write_text('[["Q"]]', encoding="utf-8")
    return path


@pytest.mark.parametrize("kind", ["fillet", "chamfer"])
@pytest.mark.parametrize("radius", [3.0, 5.0])
@pytest.mark.parametrize("size", [0.5, 1.0, 1.5])
def test_rectangle_edge_treatment_volume_formula(kind, radius, size):
    if radius > 0 and size >= radius:
        pytest.skip("size must be below the corner radius")
    poly = Polygon([(0, 0), (100, 0), (100, 40), (0, 40)])
    settings = fpg.Settings(
        corner_radius=radius,
        edge_fillet=size if kind == "fillet" else 0.0,
        edge_chamfer=size if kind == "chamfer" else 0.0,
    )
    body = fpg.extruded_footprint(
        poly, fpg.PLATE_Z_MIN, fpg.PLATE_Z_MAX - fpg.PLATE_Z_MIN, radius)
    before = body.Volume()
    body, treated = fpg.apply_edge_treatment(body, settings)
    assert treated
    assert body.isValid()
    measured = before - body.Volume()

    if kind == "fillet":
        cross_section = size * size * (1 - math.pi / 4)
        offset = size * (5 / 6 - math.pi / 4) / (1 - math.pi / 4)
    else:
        cross_section = size * size / 2
        offset = size / 3
    if radius == 0:
        effective_length = 280.0
    else:
        effective_length = 280.0 - 8 * radius + 4 * (math.pi / 2) * (radius - offset)
    expected = 2 * cross_section * effective_length
    assert abs(measured - expected) / expected < 1e-9


def test_l_shape_edge_treatment_builds_valid_body():
    l_shape = Polygon([(0, 0), (100, 0), (100, 40), (60, 40),
                       (60, 60), (0, 60)])
    settings = fpg.Settings(corner_radius=3.0, edge_fillet=1.0)
    body = fpg.extruded_footprint(
        l_shape, fpg.PLATE_Z_MIN, fpg.PLATE_Z_MAX - fpg.PLATE_Z_MIN, 3.0)
    treated, _ = fpg.apply_edge_treatment(body, settings)
    assert body.isValid()
    assert treated.isValid()
    assert treated.Volume() < body.Volume()


def test_sharp_edges_fillet_and_chamfer(one_key_layout):
    plain = build_model(one_key_layout, single_mesh=False)
    fillet = build_model(one_key_layout, single_mesh=False, edge_fillet=1.0)
    chamfer = build_model(one_key_layout, single_mesh=False, edge_chamfer=1.0)
    assert plain.plate.isValid()
    assert fillet.plate.isValid()
    assert chamfer.plate.isValid()
    assert fillet.plate.Volume() < plain.plate.Volume()
    assert chamfer.plate.Volume() < plain.plate.Volume()
    assert fillet.plate.BoundingBox().xlen == plain.plate.BoundingBox().xlen


def test_cavity_volumes_and_centers_are_unchanged(one_key_layout):
    plain = build_model(one_key_layout, single_mesh=False)
    fillet = build_model(one_key_layout, single_mesh=False, edge_fillet=0.5)
    assert len(plain.cavities) == len(fillet.cavities)
    assert abs(sum(c.Volume() for c in plain.cavities)
               - sum(c.Volume() for c in fillet.cavities)) < 1e-9
    assert fillet.centers == plain.centers


def test_cutout_warning_threshold(one_key_layout):
    warned = build_model(one_key_layout, single_mesh=False, margin=0.5,
                         edge_fillet=2.5)
    assert warned.edge_warnings
    safe = build_model(one_key_layout, single_mesh=False, margin=0.5,
                       edge_fillet=0.5)
    assert safe.edge_warnings == []


@pytest.mark.parametrize("kind", ["fillet", "chamfer"])
def test_edge_treated_stl_checks(kind, one_key_layout, tmp_path):
    model = build_model(
        one_key_layout, single_mesh=False,
        edge_fillet=1.0 if kind == "fillet" else 0.0,
        edge_chamfer=1.0 if kind == "chamfer" else 0.0,
    )
    assert model.plate.isValid()
    from tests.test_plate import export_mesh
    path = tmp_path / f"{kind}.stl"
    mesh = export_mesh(model, path)
    _, problems = fpg.check_exported_stl(
        path,
        expected_bounds=((model.plate.BoundingBox().xmin,
                          model.plate.BoundingBox().ymin,
                          model.plate.BoundingBox().zmin),
                         (model.plate.BoundingBox().xmax,
                          model.plate.BoundingBox().ymax,
                          model.plate.BoundingBox().zmax)),
    )
    assert problems == []
    assert mesh.is_watertight


def test_invalid_edge_settings():
    with pytest.raises(ValueError, match="cannot both be set"):
        fpg.Settings(edge_fillet=1, edge_chamfer=1)
    with pytest.raises(ValueError, match="half the plate thickness"):
        fpg.Settings(edge_fillet=3.1)
    with pytest.raises(ValueError, match="corner_radius"):
        fpg.Settings(corner_radius=1, edge_fillet=2)
    with pytest.raises(ValueError, match="edge_fillet"):
        fpg.Settings(edge_fillet=-1)
    with pytest.raises(ValueError, match="edge_chamfer"):
        fpg.Settings(edge_chamfer=float("inf"))


def test_edge_config_precedence(tmp_path, one_key_layout):
    config = tmp_path / "edges.toml"
    config.write_text("edge_fillet = 1.0\nedge_chamfer = 0.0\n",
                      encoding="utf-8")
    parser = fpg.build_parser()
    default_args = parser.parse_args(["--json", str(one_key_layout)])
    assert fpg.settings_from_args(default_args).edge_fillet == 0.0
    config_args = parser.parse_args(["--config", str(config),
                                     "--json", str(one_key_layout)])
    assert fpg.settings_from_args(config_args).edge_fillet == 1.0
    cli_args = parser.parse_args(["--config", str(config),
                                  "--json", str(one_key_layout),
                                  "--edge-fillet", "1.5"])
    assert fpg.settings_from_args(cli_args).edge_fillet == 1.5


@pytest.fixture
def three_key_layout(tmp_path):
    path = tmp_path / "three-key-edge.json"
    path.write_text('[["Q", "W", "E"]]', encoding="utf-8")
    return path


@pytest.mark.parametrize("kind", ["fillet", "chamfer"])
def test_every_key_keeps_its_cutout_with_edge_treatment(kind, three_key_layout):
    """Regression: the edge-warning loop reused the name of the fused cavity, so the
    plate was cut with the LAST key's cutout only and all other sockets were missing."""
    import cadquery as cq

    plain = build_model(three_key_layout, single_mesh=False)
    treated = build_model(
        three_key_layout, single_mesh=False,
        edge_fillet=1.0 if kind == "fillet" else 0.0,
        edge_chamfer=1.0 if kind == "chamfer" else 0.0)
    assert len(treated.cavities) == len(treated.keys) == 3
    for cx, cy in treated.centers:
        assert not treated.plate.isInside(cq.Vector(cx, cy, 0.0)), (cx, cy)
    # The plate is the plain plate minus the edge material, never more than that.
    assert treated.plate.Volume() < plain.plate.Volume()
    removed_by_edges = plain.plate.Volume() - treated.plate.Volume()
    assert removed_by_edges < 0.1 * plain.plate.Volume()
