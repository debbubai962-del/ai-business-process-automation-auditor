"""Safe file loading. No Streamlit imports here."""
import io
from pathlib import Path

import pandas as pd

MAX_FILE_MB = 50
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class LoadError(Exception):
    """Raised with a business-friendly message when a file cannot be loaded."""


def _read_csv(raw: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding, low_memory=False)
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            raise LoadError("The file is empty.")
        except pd.errors.ParserError as exc:
            raise LoadError(f"The file could not be parsed as CSV: {exc}")
    raise LoadError("The file encoding is not supported. Please save it as UTF-8 CSV.")


def list_excel_sheets(raw: bytes) -> list[str]:
    try:
        return pd.ExcelFile(io.BytesIO(raw)).sheet_names
    except Exception as exc:
        raise LoadError(f"The Excel file could not be opened: {exc}")


def load_bytes(filename: str, raw: bytes, sheet: str | None = None) -> pd.DataFrame:
    """Load an uploaded file into a DataFrame, with validation."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise LoadError(f"Unsupported file type '{ext}'. Please upload a CSV or Excel file.")
    if len(raw) > MAX_FILE_MB * 1024 * 1024:
        raise LoadError(f"The file is larger than {MAX_FILE_MB} MB.")
    if len(raw) == 0:
        raise LoadError("The file is empty.")

    if ext == ".csv":
        df = _read_csv(raw)
    else:
        try:
            df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet or 0)
        except Exception as exc:
            raise LoadError(f"The Excel file could not be read: {exc}")

    if df.empty or df.shape[1] == 0:
        raise LoadError("The file contains no data rows.")
    return df