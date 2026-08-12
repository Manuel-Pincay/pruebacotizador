from app.services.raw_material_service import parse_raw_material_qty


def test_parse_raw_material_qty_fractions():
    assert parse_raw_material_qty("0.5") == 0.5
    assert parse_raw_material_qty("0,25") == 0.25
    assert parse_raw_material_qty("1") == 1.0
    assert parse_raw_material_qty("") is None


def test_parse_raw_material_qty_rejects_zero():
    try:
        parse_raw_material_qty("0")
        assert False, "expected ValueError"
    except ValueError:
        pass
