from pathlib import Path

import pandas as pd
from pyprojroot import here

ROOT_DIR = here()
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".xlsm"}


def convert_workbook(input_path: Path) -> Path:
    """Convert an Excel workbook in data/raw into a CSV in data/processed."""
    dataframe = pd.read_excel(input_path, engine="openpyxl")
    output_path = PROCESSED_DIR / f"{input_path.stem}.csv"
    dataframe.to_csv(output_path, index=False)
    return output_path


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(path for path in RAW_DIR.iterdir() if path.is_file())
    if not files:
        print("No input files found in data/raw.")
        return

    print(f"Found {len(files)} input file(s) in {RAW_DIR.relative_to(ROOT_DIR)}")

    converted_count = 0
    for input_path in files:
        if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(f"[SKIP] {input_path.name} (unsupported extension)")
            continue

        try:
            output_path = convert_workbook(input_path)
            converted_count += 1
            print(f"[OK] {input_path.name} -> {output_path.relative_to(ROOT_DIR)}")
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"[ERROR] {input_path.name}: {exc}")

    print(f"Completed: {converted_count}/{len(files)} file(s) converted.")


if __name__ == "__main__":
    main()
