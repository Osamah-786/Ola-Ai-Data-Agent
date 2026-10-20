# ```python
import os
from pathlib import Path
import requests
import pandas as pd

from groq import Groq
from dotenv import load_dotenv
from utils.safe_http import UnsafeInputError, request_json, resolve_data_path


class ETLTools:
    def __init__(self):
        # Load environment variables from the project root.
        self.project_root = Path(__file__).resolve().parent.parent

        load_dotenv(
            self.project_root / ".env"
        )

    def extract_load(
        self,
        url: str,
        output_folder: str,
        format: str = "json"
    ) -> str:
        """
        Extract data from an API and save it as CSV, JSON, or Parquet.

        Args:
            url: API endpoint URL.
            output_folder: Relative to project root or absolute path.
            format: csv, json, or parquet.

        Returns:
            Status message with output path and record count.
        """
        try:
            output_format = format.lower().strip()

            if output_format not in {"csv", "json", "parquet"}:
                return f"Unsupported format: {format}"

            folder_path = resolve_data_path(self.project_root, output_folder)

            os.makedirs(folder_path, exist_ok=True)

            # Fetch API response.
            with requests.Session() as session:
                data, _, _ = request_json(session, url)

            # Normalize common API response structures.
            if isinstance(data, dict) and "results" in data:
                records = data["results"]

                if not isinstance(records, list):
                    return (
                        "Unsupported API response: "
                        "'results' must contain a list."
                    )

                df = pd.json_normalize(records)

            elif isinstance(data, list):
                df = pd.json_normalize(data)

            elif isinstance(data, dict):
                df = pd.json_normalize([data])

            else:
                return (
                    "Unsupported API response type: "
                    f"{type(data).__name__}"
                )

            if len(df) > 100_000:
                return "Extraction stopped: record limit of 100,000 exceeded."

            filename = folder_path / f"extracted_data.{output_format}"

            # Save the extracted data.
            if output_format == "csv":
                df.to_csv(filename, index=False)

            elif output_format == "json":
                # JSON Lines format.
                df.to_json(
                    filename,
                    orient="records",
                    lines=True
                )

            elif output_format == "parquet":
                df.to_parquet(
                    filename,
                    index=False
                )

            return (
                "Data successfully extracted and saved.\n"
                f"File: {filename}\n"
                f"Total records: {len(df)}"
            )

        except (requests.exceptions.RequestException, UnsafeInputError) as e:
            return f"Failed to extract data: {e}"

        except ValueError as e:
            return f"Failed to parse API response: {e}"

        except (OSError, ImportError) as e:
            return f"Failed to save extracted data: {e}"

        except Exception as e:
            return f"Unexpected extraction error: {e}"

    def transform_load_context(
        self,
        file_path: str
    ) -> str:
        """
        Read CSV, JSON Lines, or Parquet data and return
        its metadata and first three rows as AI-agent context.
        """
        try:
            file_path = resolve_data_path(self.project_root, file_path)

            if not file_path.is_file():
                return f"File not found: {file_path}"

            if file_path.stat().st_size > 50 * 1024 * 1024:
                return "Input file exceeds the 50 MiB limit."

            file_extension = file_path.suffix.lower()

            if file_extension == ".csv":
                df = pd.read_csv(file_path)

            elif file_extension == ".json":
                # Matches the JSON Lines output above.
                df = pd.read_json(
                    file_path,
                    lines=True
                )

            elif file_extension == ".parquet":
                df = pd.read_parquet(file_path)

            else:
                return (
                    f"Unsupported file format: {file_extension}. "
                    "Supported formats: .csv, .json, .parquet"
                )

            if df.empty:
                return (
                    f"File: {file_path}\n"
                    "The file contains no records."
                )

            preview = df.head(3).to_string(index=False)

            return (
                f"File: {file_path}\n"
                f"Total rows: {len(df)}\n"
                f"Total columns: {len(df.columns)}\n"
                f"Columns: {', '.join(map(str, df.columns))}\n\n"
                f"First 3 rows:\n{preview}"
            )

        except (OSError, ValueError, ImportError, UnsafeInputError) as e:
            return f"Failed to read data: {e}"

        except Exception as e:
            return f"Unexpected data-reading error: {e}"

    def list_groq_models(self) -> str:
        """
        List models available to the configured Groq API key.
        """
        try:
            api_key = os.getenv("GROQ_API_KEY")

            if not api_key:
                return (
                    "GROQ_API_KEY not found. "
                    "Check your project-root .env file."
                )

            client = Groq(api_key=api_key)
            models = client.models.list().data

            if not models:
                return "No models were returned by Groq."

            model_ids = sorted(
                model.id for model in models
            )

            return (
                "Available Groq models:\n"
                + "\n".join(model_ids)
            )

        except Exception as e:
            return f"Failed to list Groq models: {e}"

if __name__ == "__main__":
    tools = ETLTools()

    print("=== Available Groq Models ===")
    print(tools.list_groq_models())

    print("\n=== ETL Example ===")

    # Extract example API data.
    url = "https://pokeapi.co/api/v2/pokemon/1"

    result = tools.extract_load(
        url=url,
        output_folder="data/extract",
        format="json"
    )
    print(result)

    # Read the extracted data.
    file_path = os.path.join(
        "data",
        "extract",
        "extracted_data.json"
    )

    context = tools.transform_load_context(file_path)

    print("\n=== Data Context ===")
    print(context)
