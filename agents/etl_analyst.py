
import os
import sys
import json
import re
from pathlib import Path

import pandas as pd
import requests

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain.tools import tool
from langgraph.graph import StateGraph, START, END

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from models.schema import ETLAgentSchema


# ============================================================
# GROQ MODEL
# ============================================================

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError(
        "GROQ_API_KEY is missing. Add it to your project-root .env file."
    )

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    api_key=api_key,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

SUPPORTED_FORMATS = {"csv", "json", "parquet"}


def resolve_path(path: str) -> Path:
    """Resolve a relative path against the project root."""
    candidate = Path(path)

    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate

    return candidate.resolve()


def save_dataframe(df: pd.DataFrame, file_path: Path) -> None:
    """Save a DataFrame in a supported format."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    extension = file_path.suffix.lower()

    if extension == ".csv":
        df.to_csv(file_path, index=False)

    elif extension == ".json":
        df.to_json(
            file_path,
            orient="records",
            lines=True,
            force_ascii=False,
        )

    elif extension == ".parquet":
        df.to_parquet(file_path, index=False)

    else:
        raise ValueError(f"Unsupported output extension: {extension}")


def read_dataframe(file_path: Path) -> pd.DataFrame:
    """Load CSV, JSON Lines, or Parquet data."""
    extension = file_path.suffix.lower()

    if extension == ".csv":
        return pd.read_csv(file_path)

    if extension == ".json":
        return pd.read_json(file_path, lines=True)

    if extension == ".parquet":
        return pd.read_parquet(file_path)

    raise ValueError(
        "Supported input formats: .csv, .json, .parquet"
    )


# ============================================================
# TOOL 1: EXTRACT AND LOAD
# ============================================================

@tool
def extract_load_tool(
    url: str,
    output_folder: str,
    format: str = "json",
) -> str:
    """
    Extract API data and save it as CSV, JSON Lines, or Parquet.

    Follows common paginated API responses containing 'results' and
    'next', including the Pokémon API.

    Args:
        url: API endpoint URL.
        output_folder: Destination folder, relative to the project root
            or an absolute path.
        format: Output format: csv, json, or parquet.
    """
    try:
        output_format = format.strip().lower()

        if output_format not in SUPPORTED_FORMATS:
            return (
                f"Unsupported format: {format}. "
                "Use csv, json, or parquet."
            )

        output_path = resolve_path(output_folder)

        if output_path.exists() and not output_path.is_dir():
            return f"Output folder path is a file: {output_path}"

        output_path.mkdir(parents=True, exist_ok=True)

        records = []
        next_url = url
        visited_urls = set()
        max_pages = 1000
        page_count = 0

        with requests.Session() as session:
            while next_url:
                if next_url in visited_urls:
                    return "Extraction stopped: pagination URL repeated."

                if page_count >= max_pages:
                    return (
                        f"Extraction stopped after {max_pages} pages. "
                        "Use a smaller dataset or a narrower API query."
                    )

                visited_urls.add(next_url)

                response = session.get(
                    next_url,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                page_count += 1

                if isinstance(data, list):
                    records.extend(data)
                    next_url = None

                elif isinstance(data, dict):
                    if isinstance(data.get("results"), list):
                        records.extend(data["results"])
                        next_url = data.get("next")

                    elif page_count == 1:
                        # A single object, not a paginated collection.
                        records.append(data)
                        next_url = None

                    else:
                        return (
                            "Unsupported response structure on "
                            f"page {page_count}."
                        )

                else:
                    return (
                        "Unsupported API response type: "
                        f"{type(data).__name__}"
                    )

        df = pd.json_normalize(records)

        output_file = (
            output_path / f"extracted_data.{output_format}"
        )

        save_dataframe(df, output_file)

        return (
            "Extraction completed successfully.\n"
            f"File: {output_file}\n"
            f"Pages fetched: {page_count}\n"
            f"Total records: {len(df)}\n"
            f"Columns: {', '.join(map(str, df.columns))}"
        )

    except requests.exceptions.RequestException as exc:
        return f"API request failed: {exc}"

    except (ValueError, OSError, ImportError) as exc:
        return f"Extraction or saving failed: {exc}"

    except Exception as exc:
        return (
            f"Unexpected extraction error: "
            f"{type(exc).__name__}: {exc}"
        )


# ============================================================
# TOOL 2: TRANSFORM AND LOAD
# ============================================================

@tool
def transform_load_tool(
    input_file_path: str,
    output_folder: str,
    output_format: str,
    user_question: str,
) -> str:
    """
    Transform a CSV, JSON Lines, or Parquet dataset according to
    the user's request and save the transformed dataset.

    Supported operations include selecting or dropping columns,
    renaming columns, filtering rows, sorting, removing duplicates,
    and filling missing values.

    Args:
        input_file_path: Source dataset path.
        output_folder: Destination directory.
        output_format: csv, json, or parquet.
        user_question: Requested transformation.
    """
    try:
        output_format = output_format.strip().lower()

        if output_format not in SUPPORTED_FORMATS:
            return f"Unsupported output format: {output_format}"

        input_path = resolve_path(input_file_path)
        output_dir = resolve_path(output_folder)

        if not input_path.is_file():
            return f"Input file not found: {input_path}"

        if not output_dir.is_dir() and output_dir.exists():
            return f"Output path is not a directory: {output_dir}"

        df = read_dataframe(input_path)

        if df.empty:
            return "The input dataset contains no records."

        columns = list(df.columns)

        # Ask the LLM for a JSON transformation plan, not executable code.
        prompt = f"""
You are a data transformation planner.

Return ONLY a valid JSON object with this structure:
{{
  "operations": [
    {{"type": "select_columns", "columns": ["column_name"]}}
  ]
}}

Choose operations that satisfy the user's request.

Allowed operation types and arguments:

1. select_columns:
   {{"type":"select_columns","columns":["name"]}}

2. drop_columns:
   {{"type":"drop_columns","columns":["name"]}}

3. rename_columns:
   {{"type":"rename_columns","mapping":{{"old_name":"new_name"}}}}

4. drop_duplicates:
   {{"type":"drop_duplicates","columns":["name"]}}
   The columns field is optional.

5. sort_values:
   {{"type":"sort_values","column":"name","ascending":true}}

6. filter_rows:
   {{"type":"filter_rows","column":"age","operator":">=","value":18}}
   Operators: ==, !=, >, >=, <, <=, contains

7. fillna:
   {{"type":"fillna","column":"name","value":"Unknown"}}

Rules:
- Use only the allowed operation types.
- Use the exact column names provided.
- Return an empty operations list if no transformation is needed.
- Do not invent columns.
- For numeric filters, use numeric values.
- For text filters, use strings.
- Do not include Markdown fences or extra text.

Available columns:
{json.dumps([str(c) for c in columns])}

Dataset sample:
{df.head(3).to_json(orient="records", force_ascii=False)}

User request:
{user_question}
"""

        response = llm.invoke(prompt).content

        if isinstance(response, list):
            response = "".join(
                item.get("text", "")
                for item in response
                if isinstance(item, dict)
            )

        response = str(response).strip()

        # Allow JSON enclosed in Markdown fences.
        response = re.sub(
            r"^```(?:json)?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )
        response = re.sub(r"\s*```$", "", response).strip()

        plan = json.loads(response)

        if not isinstance(plan, dict):
            return "Invalid transformation plan: expected a JSON object."

        operations = plan.get("operations")

        if not isinstance(operations, list):
            return "Invalid transformation plan: operations must be a list."

        if len(operations) > 30:
            return "Transformation rejected: too many operations."

        applied_operations = []

        for operation in operations:
            if not isinstance(operation, dict):
                return "Invalid transformation operation."

            operation_type = operation.get("type")

            if operation_type == "select_columns":
                selected = operation.get("columns")

                if not isinstance(selected, list) or not selected:
                    return "select_columns requires a non-empty columns list."

                missing = [c for c in selected if c not in df.columns]
                if missing:
                    return f"Unknown columns: {missing}"

                df = df[selected]
                applied_operations.append(operation_type)

            elif operation_type == "drop_columns":
                selected = operation.get("columns")

                if not isinstance(selected, list):
                    return "drop_columns requires a columns list."

                missing = [c for c in selected if c not in df.columns]
                if missing:
                    return f"Unknown columns: {missing}"

                df = df.drop(columns=selected)
                applied_operations.append(operation_type)

            elif operation_type == "rename_columns":
                mapping = operation.get("mapping")

                if not isinstance(mapping, dict):
                    return "rename_columns requires a mapping object."

                missing = [c for c in mapping if c not in df.columns]
                if missing:
                    return f"Unknown columns to rename: {missing}"

                new_names = list(mapping.values())

                if len(new_names) != len(set(new_names)):
                    return "Rename rejected: duplicate destination column names."

                unaffected = [
                    c for c in df.columns if c not in mapping
                ]

                if set(new_names) & set(unaffected):
                    return (
                        "Rename rejected: a destination column name "
                        "already exists."
                    )

                df = df.rename(columns=mapping)
                applied_operations.append(operation_type)

            elif operation_type == "drop_duplicates":
                selected = operation.get("columns")

                if selected is not None:
                    if not isinstance(selected, list):
                        return "drop_duplicates columns must be a list."

                    missing = [
                        c for c in selected if c not in df.columns
                    ]
                    if missing:
                        return f"Unknown columns: {missing}"

                df = df.drop_duplicates(subset=selected)
                applied_operations.append(operation_type)

            elif operation_type == "sort_values":
                column = operation.get("column")

                if column not in df.columns:
                    return f"Unknown sort column: {column}"

                ascending = operation.get("ascending", True)

                if not isinstance(ascending, bool):
                    return "ascending must be true or false."

                df = df.sort_values(
                    by=column,
                    ascending=ascending,
                )
                applied_operations.append(operation_type)

            elif operation_type == "filter_rows":
                column = operation.get("column")
                operator = operation.get("operator")
                value = operation.get("value")

                if column not in df.columns:
                    return f"Unknown filter column: {column}"

                if operator not in {"==", "!=", ">", ">=", "<", "<=", "contains"}:
                    return f"Unsupported filter operator: {operator}"

                series = df[column]

                if operator == "contains":
                    mask = series.astype("string").str.contains(
                        str(value),
                        case=False,
                        na=False,
                        regex=False,
                    )
                elif operator == "==":
                    mask = series == value
                elif operator == "!=":
                    mask = series != value
                else:
                    numeric_series = pd.to_numeric(
                        series,
                        errors="coerce",
                    )

                    try:
                        numeric_value = float(value)
                    except (TypeError, ValueError):
                        return (
                            f"Numeric comparison requires a number: {value}"
                        )

                    if operator == ">":
                        mask = numeric_series > numeric_value
                    elif operator == ">=":
                        mask = numeric_series >= numeric_value
                    elif operator == "<":
                        mask = numeric_series < numeric_value
                    else:
                        mask = numeric_series <= numeric_value

                df = df.loc[mask].copy()
                applied_operations.append(operation_type)

            elif operation_type == "fillna":
                column = operation.get("column")

                if column not in df.columns:
                    return f"Unknown fillna column: {column}"

                if "value" not in operation:
                    return "fillna requires a value."

                df[column] = df[column].fillna(operation["value"])
                applied_operations.append(operation_type)

            else:
                return f"Unsupported transformation: {operation_type}"

        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = (
            output_dir / f"transformed_data.{output_format}"
        )

        # Avoid overwriting an existing file.
        if output_file.exists():
            return (
                f"Output file already exists: {output_file}\n"
                "Choose another output folder or move the existing file."
            )

        save_dataframe(df, output_file)

        return (
            "Transformation completed successfully.\n"
            f"Input: {input_path}\n"
            f"Output: {output_file}\n"
            f"Rows after transformation: {len(df)}\n"
            f"Columns after transformation: {len(df.columns)}\n"
            f"Applied operations: {applied_operations or 'None'}"
        )

    except json.JSONDecodeError as exc:
        return f"Could not parse the LLM transformation plan: {exc}"

    except (OSError, ValueError, ImportError) as exc:
        return f"Transformation failed: {exc}"

    except Exception as exc:
        return (
            f"Unexpected transformation error: "
            f"{type(exc).__name__}: {exc}"
        )


# ============================================================
# BIND TOOLS
# ============================================================

tools = [
    extract_load_tool,
    transform_load_tool,
]

tools_by_name = {
    item.name: item
    for item in tools
}

llm_bind = llm.bind_tools(tools)


# ============================================================
# AGENT SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an ETL data analyst working in a LangGraph workflow.

Available tools:
- extract_load_tool: fetch API data and save it to a file.
- transform_load_tool: transform an existing dataset and save the result.

Rules:
1. Use extract_load_tool for API extraction.
2. Use transform_load_tool for dataset transformation.
3. Ask for clarification when a required argument is missing.
4. Use only CSV, JSON, or Parquet output formats.
5. Do not claim an operation succeeded unless a tool confirms success.
6. After a tool call, inspect its returned result before responding.
7. If a tool fails, clearly report the failure.
8. Do not invent file paths or dataset contents.
"""


# ============================================================
# LANGGRAPH NODES
# ============================================================

def llm_node(state: ETLAgentSchema):
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *state.messages,
    ]

    answer = llm_bind.invoke(messages)

    return {
        "messages": [answer]
    }


def tool_node(state: ETLAgentSchema):
    last_message = state.messages[-1]
    tool_results = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]

        if tool_name not in tools_by_name:
            result = f"Unknown tool: {tool_name}"
        else:
            try:
                result = tools_by_name[tool_name].invoke(tool_args)
            except Exception as exc:
                result = (
                    f"Tool failed: {type(exc).__name__}: {exc}"
                )

        tool_results.append(
            ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id,
            )
        )

    return {
        "messages": tool_results
    }


def is_tool_call(state: ETLAgentSchema):
    last_message = state.messages[-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tool_node"

    return END


# ============================================================
# BUILD LANGGRAPH
# ============================================================

builder = StateGraph(ETLAgentSchema)

builder.add_node("llm_node", llm_node)
builder.add_node("tool_node", tool_node)

builder.add_edge(START, "llm_node")

builder.add_conditional_edges(
    "llm_node",
    is_tool_call,
    {
        "tool_node": "tool_node",
        END: END,
    },
)

builder.add_edge("tool_node", "llm_node")

etl_analyst = builder.compile()


# ============================================================
# RUN AGENT
# ============================================================

if __name__ == "__main__":
    print("Starting ETL Agent...")

    # Example: fetch the first page and follow API pagination.
    user_request = (
        "Extract data from https://pokeapi.co/api/v2/pokemon "
        "and save it to data/extract in CSV format."
    )

    try:
        response = etl_analyst.invoke(
            {
                "messages": [
                    HumanMessage(content=user_request)
                ]
            },
            config={
                "recursion_limit": 30
            },
        )

        print("\nETL Agent Response:\n")

        for message in response["messages"]:
            if isinstance(message, AIMessage) and message.content:
                print(message.content)

    except Exception as exc:
        print(
            f"Agent execution failed: "
            f"{type(exc).__name__}: {exc}"
        )
