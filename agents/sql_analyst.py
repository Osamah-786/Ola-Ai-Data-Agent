
import os
import sys
import re
import json
from pathlib import Path

from dotenv import load_dotenv
from psycopg2 import connect, sql as pg_sql
from psycopg2.extras import RealDictCursor

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from utils.llm_pick import pick_llm
from utils.database import DatabaseUtil
from models.schema import AgentSchema, JudgeSchema

load_dotenv()


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

def get_db_config():
    required = ["host", "user", "password", "database"]

    missing = [key for key in required if not os.getenv(key)]

    if missing:
        raise ValueError(
            f"Missing database settings in .env: {', '.join(missing)}"
        )

    return {
        "host": os.getenv("host"),
        "port": int(os.getenv("port", "5432")),
        "user": os.getenv("user"),
        "password": os.getenv("password"),
        "dbname": os.getenv("database"),
        "connect_timeout": 10,
    }


# ============================================================
# SQL HELPERS
# ============================================================

def clean_sql(query: str) -> str:
    """Remove common Markdown SQL fences from model output."""

    query = query.strip()

    query = re.sub(
        r"^```(?:sql)?\s*",
        "",
        query,
        flags=re.IGNORECASE,
    )
    query = re.sub(r"\s*```$", "", query)

    return query.strip()


def validate_read_only_sql(query: str) -> tuple[bool, str]:
    """
    Basic SQL validation.

    The PostgreSQL read-only transaction in execute_sql()
    provides an additional database-level protection.
    """

    if not query or not query.strip():
        return False, "The generated SQL query is empty."

    query = clean_sql(query)

    # Reject comments to reduce ambiguity in generated SQL.
    if "--" in query or "/*" in query or "*/" in query:
        return False, "SQL comments are not permitted."

    # Allow one optional trailing semicolon, but no multiple statements.
    statement = query.rstrip().removesuffix(";").strip()

    if not statement:
        return False, "The SQL query is empty."

    if ";" in statement:
        return False, "Multiple SQL statements are not permitted."

    # Only SELECT and WITH statements are accepted.
    if not re.match(r"^(SELECT|WITH)\b", statement, re.IGNORECASE):
        return False, "Only SELECT queries are allowed."

    forbidden = re.compile(
        r"\b("
        r"INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|"
        r"GRANT|REVOKE|COPY|CALL|DO|EXECUTE|"
        r"MERGE|VACUUM|ANALYZE|REFRESH|"
        r"INTO|LOCK|SET|RESET"
        r")\b",
        re.IGNORECASE,
    )

    if forbidden.search(statement):
        return False, "The query contains a prohibited SQL keyword."

    return True, "Basic SQL validation passed."


# ============================================================
# NODE 1: CURATE THE USER QUESTION
# ============================================================

def curate_question(state: AgentSchema) -> AgentSchema:

    user_question = state.user_question

    llm = pick_llm("low")

    response = llm.invoke(
        "Rewrite the following database question clearly without "
        "changing its meaning. Return only the rewritten question.\n\n"
        f"Question: {user_question}"
    )

    state.curated_ques = response.content.strip()

    state.messages = list(state.messages or []) + [
        HumanMessage(content=user_question),
        AIMessage(content=state.curated_ques),
    ]

    return state


# ============================================================
# NODE 2: RETRIEVE DATABASE SCHEMA
# ============================================================

def prompt_query_context(state: AgentSchema) -> AgentSchema:

    db_config = get_db_config()

    # DatabaseUtil expects the psycopg2 connection argument 'dbname'.
    db_util = DatabaseUtil(db_config)

    try:
        schema_info = db_util.schema_details("public")
    finally:
        db_util.close()

    if schema_info.startswith("Error"):
        raise RuntimeError(
            f"Could not retrieve database schema: {schema_info}"
        )

    prompt = f"""
You are a PostgreSQL SQL analyst.

Convert the user's question into one valid PostgreSQL query.

Rules:
1. Generate a single read-only SELECT query.
2. Do not generate INSERT, UPDATE, DELETE, DROP, ALTER,
   TRUNCATE, CREATE, or any other data-changing operation.
3. Use only tables and columns present in the supplied schema.
4. Use correct PostgreSQL syntax.
5. Unless the user explicitly requests a different number,
   limit the result to 10 rows.
6. For questions about distinct categories, use DISTINCT.
7. Do not invent table names, columns, or values.
8. Return only SQL, without Markdown fences or explanations.

User question:
{state.curated_ques}

Database schema:
{schema_info}
"""

    state.prompt_query_context = prompt

    return state


# ============================================================
# NODE 3: GENERATE SQL
# ============================================================

def generate_sql(state: AgentSchema) -> AgentSchema:

    llm = pick_llm("medium")

    response = llm.invoke(state.prompt_query_context)

    generated_query = clean_sql(response.content)

    state.generated_sql_query = generated_query

    return state


# ============================================================
# NODE 4: CHECK SQL SAFETY
# ============================================================

def is_safe_sql(state: AgentSchema) -> AgentSchema:

    query = state.generated_sql_query

    # First perform deterministic checks.
    valid, reason = validate_read_only_sql(query)

    if not valid:
        state.is_safe = "No"
        state.comments = reason
        return state

    # Then ask the structured-output LLM judge.
    try:
        llm = pick_llm("medium")
        llm_judge = llm.with_structured_output(JudgeSchema)

        prompt = f"""
You are a database security reviewer.

Determine whether this PostgreSQL query is strictly read-only
and suitable for execution.

Reject:
- Data-changing or schema-changing operations.
- Multiple statements.
- Queries that attempt to modify database state.
- Dangerous or ambiguous operations.

Return the required JudgeSchema fields.
If uncertain, reject the query.

SQL query:
{query}
"""

        result = llm_judge.invoke(prompt)

        answer = str(result.answer).strip().lower()

        if answer in {"yes", "true"}:
            state.is_safe = "Yes"
            state.comments = str(result.comments)
        else:
            state.is_safe = "No"
            state.comments = str(result.comments)

    except Exception as exc:
        # Fail closed if the safety judge fails.
        state.is_safe = "No"
        state.comments = (
            f"SQL safety review failed; query rejected: {exc}"
        )

    return state


# ============================================================
# NODE 5: REJECT UNSAFE SQL
# ============================================================

def canceled_sql(state: AgentSchema) -> AgentSchema:

    state.final_answer = (
        "The generated SQL query was not executed because it "
        f"failed the safety checks. Reason: {state.comments}"
    )

    state.messages = list(state.messages or []) + [
        AIMessage(content=state.final_answer)
    ]

    return state


# ============================================================
# NODE 6: EXECUTE SQL IN A READ-ONLY TRANSACTION
# ============================================================

def execute_sql(state: AgentSchema) -> AgentSchema:

    query = clean_sql(state.generated_sql_query)

    # Validate again immediately before execution.
    valid, reason = validate_read_only_sql(query)

    if not valid:
        state.sql_query_execution_result = (
            f"Query rejected: {reason}"
        )
        state.final_answer = (
            "The query was rejected by the final SQL validation check."
        )
        return state

    connection = None
    cursor = None

    try:
        connection = connect(**get_db_config())

        # Prevent database modifications even if an earlier check
        # fails to recognize a dangerous statement.
        connection.set_session(readonly=True, autocommit=False)

        cursor = connection.cursor(
            cursor_factory=RealDictCursor
        )

        # Bound execution time.
        cursor.execute("SET LOCAL statement_timeout = '15s'")

        cursor.execute(query)

        if cursor.description is None:
            raise ValueError(
                "The query did not return rows. Only result-producing "
                "queries are supported."
            )

        rows = cursor.fetchmany(101)

        # Protect the agent from unexpectedly large results.
        if len(rows) > 100:
            rows = rows[:100]

        # JSON keeps values such as dates and Decimal instances transportable
        # through the API; unknown scalar types fall back to safe text values.
        state.sql_query_execution_result = json.dumps(
            [dict(row) for row in rows], default=str
        )

        connection.rollback()

    except Exception as exc:

        if connection is not None:
            connection.rollback()

        state.sql_query_execution_result = (
            f"SQL execution failed: {exc}"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

    return state


# ============================================================
# NODE 7: GENERATE FINAL ANSWER
# ============================================================

def represent_final_answer(state: AgentSchema) -> AgentSchema:

    execution_result = state.sql_query_execution_result

    # Do not ask the LLM to summarize an execution error.
    if (
        execution_result is None
        or str(execution_result).startswith(
            "SQL execution failed:"
        )
        or str(execution_result).startswith("Query rejected:")
    ):
        state.final_answer = (
            "I could not retrieve the requested information. "
            f"{execution_result}"
        )

        state.messages = list(state.messages or []) + [
            AIMessage(content=state.final_answer)
        ]

        return state

    llm = pick_llm("low")

    prompt = f"""
You are a SQL analyst assistant.

Answer the user's question using only the database result below.
Be concise, clear, and accurate.
Do not invent values or claim information that is absent.
Do not include SQL code.

User question:
{state.curated_ques}

Database execution result:
{execution_result}

If the result is empty, clearly state that no matching records
were found.
"""

    response = llm.invoke(prompt)

    state.final_answer = response.content.strip()

    state.messages = list(state.messages or []) + [
        AIMessage(content=state.final_answer)
    ]

    return state


# ============================================================
# NODE 8: ROUTE BASED ON SQL SAFETY
# ============================================================

def is_safe_sql_edge(state: AgentSchema) -> str:

    if str(state.is_safe).strip().lower() == "yes":
        return "execute_sql"

    return "canceled_sql"


# ============================================================
# BUILD LANGGRAPH WORKFLOW
# ============================================================

sql_agent_graph = StateGraph(AgentSchema)

# Register nodes using explicit names.
sql_agent_graph.add_node("curate_ques", curate_question)
sql_agent_graph.add_node(
    "prompt_query_context", prompt_query_context
)
sql_agent_graph.add_node("generate_sql", generate_sql)
sql_agent_graph.add_node("is_safe_sql", is_safe_sql)
sql_agent_graph.add_node("canceled_sql", canceled_sql)
sql_agent_graph.add_node("execute_sql", execute_sql)
sql_agent_graph.add_node(
    "represent_final_answer", represent_final_answer
)

# Main flow.
sql_agent_graph.add_edge(START, "curate_ques")
sql_agent_graph.add_edge("curate_ques", "prompt_query_context")
sql_agent_graph.add_edge(
    "prompt_query_context", "generate_sql"
)
sql_agent_graph.add_edge("generate_sql", "is_safe_sql")

# Conditional routing.
sql_agent_graph.add_conditional_edges(
    "is_safe_sql",
    is_safe_sql_edge,
    {
        "execute_sql": "execute_sql",
        "canceled_sql": "canceled_sql",
    },
)

sql_agent_graph.add_edge("canceled_sql", END)
sql_agent_graph.add_edge(
    "execute_sql", "represent_final_answer"
)
sql_agent_graph.add_edge("represent_final_answer", END)

# Compile the graph.
sql_analyst = sql_agent_graph.compile()


# ============================================================
# RUN THE AGENT
# ============================================================

if __name__ == "__main__":

    input_schema = {
        "messages": [],
        "user_question": (
            "What are the different types of payment methods "
            "we have in our database?"
        ),
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
    }

    try:
        # Invoke the workflow.
        result = sql_analyst.invoke(input_schema)

        print("\n" + "=" * 60)
        print("USER QUESTION")
        print("=" * 60)
        print(result["user_question"])

        print("\n" + "=" * 60)
        print("GENERATED SQL")
        print("=" * 60)
        print(result["generated_sql_query"])

        print("\n" + "=" * 60)
        print("SAFETY REVIEW")
        print("=" * 60)
        print("Safe:", result["is_safe"])
        print("Comments:", result["comments"])

        print("\n" + "=" * 60)
        print("EXECUTION RESULT")
        print("=" * 60)
        print(result["sql_query_execution_result"])

        print("\n" + "=" * 60)
        print("FINAL ANSWER")
        print("=" * 60)
        print(result["final_answer"])

        # Export the workflow diagram if visualization dependencies
        # are installed.
        try:
            graph_image = sql_analyst.get_graph().draw_mermaid_png()

            graph_path = Path(__file__).resolve().parents[1] / "docs" / "diagrams" / "sql_analyst_graph.png"
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            with graph_path.open("wb") as file:
                file.write(graph_image)

            print(f"\nGraph saved to {graph_path}")

        except Exception as exc:
            print(f"\nGraph image was not generated: {exc}")

    except Exception as exc:
        print(f"\nAgent failed: {exc}")
