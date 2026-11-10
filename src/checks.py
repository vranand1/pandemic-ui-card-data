"""Input checks that fail loudly, with the fix in the message, instead of failing deep inside an estimator.

The Opportunity Insights tracker is a live repository: files get renamed, columns change, and a partial
download leaves an empty CSV. Each of those used to surface as a KeyError or an all-NaN panel several steps
later. Here they raise DataError at the point of reading, naming the file and what to do.
"""
from pathlib import Path

import pandas as pd

from logsetup import get_logger

log = get_logger("checks")


class DataError(RuntimeError):
    """Raw input is missing, empty, or does not have the expected structure."""


def read_raw_csv(path: Path, required: list, **kwargs) -> pd.DataFrame:
    """Read a raw CSV and check that it exists, is non-empty and has the columns the analysis uses."""
    path = Path(path)
    if not path.exists():
        raise DataError(f"{path.name} not found in {path.parent}. Run ./get_data.sh first.")
    try:
        df = pd.read_csv(path, **kwargs)
    except pd.errors.EmptyDataError as exc:
        raise DataError(f"{path.name} is empty; the download probably failed. Re-run ./get_data.sh.") from exc
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataError(f"{path.name} is missing columns {missing}. The upstream file format may have changed; "
                        f"columns found: {list(df.columns)[:15]}")
    if df.empty:
        raise DataError(f"{path.name} has a header but no rows. Re-run ./get_data.sh.")
    log.debug("read %s: %d rows", path.name, len(df))
    return df


def check_unique(df: pd.DataFrame, keys: list, what: str) -> None:
    """A panel must have one row per key; a duplicate silently double-weights a unit."""
    dup = df.duplicated(keys, keep=False)
    if dup.any():
        raise DataError(f"{what}: {int(dup.sum())} rows share the same {keys}, e.g. "
                        f"{df.loc[dup, keys].head(3).to_dict('records')}")


def check_count(n: int, expected: int, what: str) -> None:
    """Sample sizes the design depends on (treated states, never-treated states) must not drift silently."""
    if n != expected:
        raise DataError(f"{what}: expected {expected}, found {n}. Check treatment dates in common.END and DROP.")
