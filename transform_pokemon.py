
from pathlib import Path
import pandas as pd

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent

input_file = PROJECT_ROOT / "data" / "extract" / "extracted_data.csv"
output_dir = PROJECT_ROOT / "data" / "transformed"
output_file = output_dir / "transformed_data.csv"

try:
    # Validate the input file
    if not input_file.is_file():
        raise FileNotFoundError(
            f"Input file not found: {input_file}"
        )

    # Prevent overwriting an existing file
    if output_file.exists():
        raise FileExistsError(
            f"Output already exists: {output_file}"
        )

    # Load dataset
    df = pd.read_csv(input_file)

    if "name" not in df.columns:
        raise ValueError(
            "The dataset does not contain a 'name' column."
        )

    # Filter names containing 'bulbasaur', case-insensitive
    filtered_df = df[
        df["name"].astype("string").str.contains(
            "bulbasaur",
            case=False,
            regex=False,
            na=False,
        )
    ].copy()

    # Create output directory and save results
    output_dir.mkdir(parents=True, exist_ok=True)
    filtered_df.to_csv(output_file, index=False)

    print("Transformation completed successfully!")
    print(f"Input rows: {len(df)}")
    print(f"Matching rows: {len(filtered_df)}")
    print(f"Output file: {output_file}")

    print("\nFiltered data:")
    print(filtered_df.to_string(index=False))

except (OSError, ValueError, pd.errors.ParserError) as exc:
    print(f"Transformation failed: {exc}")
