from stockpicker.security_master import load_security_mappings_csv


def test_load_security_mappings_csv(tmp_path):
    path = tmp_path / "map.csv"
    path.write_text("cusip,ticker,issuer_name\n000000001,ACME,Acme Corp\n")

    mappings = load_security_mappings_csv(path)

    assert len(mappings) == 1
    assert mappings[0].cusip == "000000001"
    assert mappings[0].ticker == "ACME"
    assert mappings[0].issuer_name == "Acme Corp"
