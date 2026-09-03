import copy

import pytest

from decision.layout import (
    LAYOUT_PRESET_CHOICES,
    PRESET_LAYOUTS,
    LayoutConfig,
    create_warehouse_for_experiment,
    create_warehouse_from_preset,
    validate_layout_config,
)
from experiment.config import ExperimentConfig
from simulation.warehouse import CellType


def make_config(**overrides) -> ExperimentConfig:
    data = {
        "seed": 1,
        "num_robots": 1,
        "stop_mode": "fixed_ticks",
        "target_tasks": None,
        "max_ticks": 5,
    }
    data.update(overrides)
    return ExperimentConfig.from_dict(data)


def test_layout_preset_choices_include_expected_presets():
    assert "default" in LAYOUT_PRESET_CHOICES
    assert "high_density" in LAYOUT_PRESET_CHOICES
    assert "one_way_aisles" in LAYOUT_PRESET_CHOICES


def test_default_preset_builds_warehouse():
    warehouse = create_warehouse_from_preset("default")

    assert warehouse.width > 0
    assert warehouse.height > 0


def test_high_density_preset_is_valid():
    warehouse = create_warehouse_from_preset("high_density")

    cell_types = {
        warehouse.cell_type(x, y)
        for y in range(warehouse.height)
        for x in range(warehouse.width)
    }

    assert CellType.CHARGING in cell_types
    assert CellType.MAINTENANCE in cell_types
    assert CellType.SHELF in cell_types
    assert CellType.RECEIVING in cell_types
    assert CellType.SHIPPING in cell_types
    assert CellType.PACKING in cell_types
    assert CellType.PICK_STATION in cell_types

    assert "PICK-1" in warehouse.locations
    assert "PACK-1" in warehouse.locations
    assert "A-01" in warehouse.locations

    # resolve() returns access coordinates.
    warehouse.resolve("PACK-1")
    warehouse.resolve("A-01")


def test_one_way_aisles_preset_is_valid():
    warehouse = create_warehouse_from_preset("one_way_aisles")

    cell_types = {
        warehouse.cell_type(x, y)
        for y in range(warehouse.height)
        for x in range(warehouse.width)
    }

    assert CellType.CHARGING in cell_types
    assert CellType.MAINTENANCE in cell_types
    assert CellType.SHELF in cell_types

    assert "A-01" in warehouse.locations
    assert "B-01" in warehouse.locations


def test_non_rectangular_layout_rejected():
    config = LayoutConfig.from_dict(
        {
            "name": "bad",
            "layout": [
                ".",
                "..",
            ],
            "locations": {},
        }
    )

    with pytest.raises(ValueError):
        validate_layout_config(config)


def test_missing_maintenance_cell_rejected():
    data = copy.deepcopy(PRESET_LAYOUTS["high_density"])

    # Remove the maintenance cell from the layout.
    data["layout"][0] = data["layout"][0].replace("X", ".")

    config = LayoutConfig.from_dict(data)

    with pytest.raises(ValueError):
        validate_layout_config(config)


def test_shelf_access_must_be_adjacent():
    data = copy.deepcopy(PRESET_LAYOUTS["high_density"])

    # Move A-01 access far away from the shelf cell.
    data["locations"]["A-01"]["access"] = [8, 2]

    config = LayoutConfig.from_dict(data)

    with pytest.raises(ValueError):
        validate_layout_config(config)


def test_experiment_config_rejects_unknown_layout_preset():
    with pytest.raises(ValueError):
        make_config(layout_preset="not_a_preset")


def test_experiment_config_default_layout_is_default():
    config = make_config()

    assert config.layout_preset == "default"
    assert config.layout_file is None


def test_create_warehouse_for_experiment_supports_presets():
    warehouse = create_warehouse_for_experiment("high_density", None)

    assert warehouse.width > 0
    assert warehouse.height > 0
    assert "A-01" in warehouse.locations