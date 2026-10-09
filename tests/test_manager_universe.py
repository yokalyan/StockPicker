from stockpicker.manager_universe import load_manager_universe_csv
from stockpicker.models import StrategyType


def test_load_manager_universe_csv_applies_strategy_defaults(tmp_path):
    path = tmp_path / "managers.csv"
    path.write_text("name,cik,strategy\nPatient Capital,12345,small_mid_value\n")

    managers = load_manager_universe_csv(path)

    assert len(managers) == 1
    assert managers[0].name == "Patient Capital"
    assert managers[0].cik == "12345"
    assert managers[0].strategy == StrategyType.SMALL_MID_VALUE
    assert managers[0].quality_score == 8.0
