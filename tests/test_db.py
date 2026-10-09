from stockpicker.db import Database
from stockpicker.models import Manager, StrategyType


def test_database_initializes_and_upserts_manager(tmp_path):
    db = Database(tmp_path / "stockpicker.sqlite")
    db.init()

    manager_id = db.upsert_manager(
        Manager(
            name="Patient Capital",
            cik="12345",
            strategy=StrategyType.SMALL_MID_VALUE,
            quality_score=8.5,
        )
    )

    assert manager_id > 0
    managers = db.managers()
    assert managers[0].name == "Patient Capital"
    assert managers[0].cik == "0000012345"
