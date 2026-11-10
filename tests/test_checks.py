"""The input checks raise DataError with an actionable message instead of failing later in an estimator."""
import pandas as pd
import pytest

from checks import DataError, check_count, check_unique, read_raw_csv


def test_missing_file_names_the_fix(tmp_path):
    with pytest.raises(DataError, match="get_data.sh"):
        read_raw_csv(tmp_path / "nope.csv", ["a"])


def test_empty_file_is_reported_as_failed_download(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("")
    with pytest.raises(DataError, match="empty"):
        read_raw_csv(p, ["a"])


def test_header_only_file_is_rejected(tmp_path):
    p = tmp_path / "header.csv"
    p.write_text("a,b\n")
    with pytest.raises(DataError, match="no rows"):
        read_raw_csv(p, ["a"])


def test_missing_columns_are_listed(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(DataError, match=r"\['c'\]"):
        read_raw_csv(p, ["a", "c"])


def test_valid_file_reads_with_pandas_options(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,.\n")
    df = read_raw_csv(p, ["a", "b"], na_values=".")
    assert df.b.isna().all() and df.a.iloc[0] == 1


def test_check_unique_flags_duplicate_keys():
    df = pd.DataFrame({"state": [1, 1, 2], "week": ["w1", "w1", "w1"]})
    with pytest.raises(DataError, match="2 rows"):
        check_unique(df, ["state", "week"], "panel")
    check_unique(df.drop_duplicates(), ["state", "week"], "panel")


def test_check_count():
    check_count(24, 24, "treated")
    with pytest.raises(DataError, match="expected 24, found 23"):
        check_count(23, 24, "treated")
