import pandas as pd

from scripts.process_data import parse_date_values


def test_date_parser_supports_excel_style_and_documented_string_formats():
    parsed, quality = parse_date_values(pd.Series(["11/30/25", "30-11-2025 12:30:00", "01/02/25"]))
    assert parsed.iloc[0].strftime("%Y-%m-%d") == "2025-11-30"
    assert parsed.iloc[1].strftime("%Y-%m-%d %H:%M:%S") == "2025-11-30 12:30:00"
    assert pd.isna(parsed.iloc[2])
    assert quality["ambiguous_datetime"] == 1

