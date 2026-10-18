
import os
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    BaseMessage,
)
from langgraph.graph import StateGraph, START, END

# =========================================================
# PROJECT CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from models.schema import DataAgentSchema
from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst


# =========================================================
# GROQ CONFIGURATION
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing. Check your project-root .env file."
    )

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    api_key=GROQ_API_KEY,
)


# =========================================================
# ROUTER SCHEMA
# =========================================================

class RouterSchema(BaseModel):
    answer: Literal["sql", "etl"] = Field(
        description=(
            "Return 'etl' for API extraction, file loading, "
            "dataset transformation, and file-based data processing. "
            "Return 'sql' for database queries and SQL analysis."
        )
    )


llm_router = llm.with_structured_output(RouterSchema)


# =========================================================
# STATE HELPERS
# =========================================================

def get_state_value(state, key, default=None):
    """Support dictionary and Pydantic/object-based graph states."""
    if isinstance(state, dict):
        return state.get(key, default)

    return getattr(state, key, default)


def get_latest_user_message(state) -> str:
    """Find the latest human message in the graph state."""
    messages = get_state_value(state, "messages", [])

    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return str(message.content)

    if messages:
        return str(messages[-1].content)

    raise ValueError("No messages were provided to the data agent.")


# =========================================================
# ROUTER NODE
# =========================================================

def router_node(state: DataAgentSchema):
    user_message = get_latest_user_message(state)

    router_prompt = f"""
You are a routing assistant for a data analytics application.

Choose exactly one route.

ETL:
- Extract data from an API.
- Save API data to CSV, JSON, or Parquet.
- Transform or clean datasets.
- Process files and structured data.

SQL:
- Query a SQL database.
- Retrieve database records.
- Analyze database tables.
- Perform database-related analytics.

Select the route that best matches the user's request.
Do not execute the task yourself.

User request:
{user_message}
"""

    result = llm_router.invoke(router_prompt)

    print(f"[Router] Selected route: {result.answer}")

    return {"route_response": result.answer}


# =========================================================
# ETL NODE
# =========================================================

def etl_node(state: DataAgentSchema):
    user_message = get_latest_user_message(state)

    print("[ETL] Processing request...")

    response = etl_analyst.invoke(
        {
            "messages": [
                HumanMessage(content=user_message)
            ]
        },
        config={"recursion_limit": 30},
    )

    # Retrieve the final AI response from the ETL subgraph.
    final_message = next(
        (
            message
            for message in reversed(response["messages"])
            if isinstance(message, AIMessage) and message.content
        ),
        None,
    )

    if final_message is None:
        answer = "The ETL agent did not return a final response."
    else:
        answer = final_message.content

    return {
        "messages": [
            AIMessage(content=f"ETL Agent Result:\n{answer}")
        ]
    }


# =========================================================
# SQL NODE
# =========================================================

def sql_node(state: DataAgentSchema):
    user_message = get_latest_user_message(state)

    print("[SQL] Processing request...")

    sql_input = {
        "messages": [
            HumanMessage(content=user_message)
        ],
        "user_question": user_message,
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
    }

    response = sql_analyst.invoke(
        sql_input,
        config={"recursion_limit": 30},
    )

    if isinstance(response, dict):
        answer = (
            response.get("final_answer")
            or response.get("sql_query_execution_result")
            or response.get("comments")
            or "The SQL agent returned no final answer."
        )
    else:
        answer = str(response)

    return {
        "messages": [
            AIMessage(content=f"SQL Agent Result:\n{answer}")
        ]
    }


# =========================================================
# ROUTING LOGIC
# =========================================================

def route_edge(state: DataAgentSchema) -> str:
    route = get_state_value(state, "route_response")

    if route == "sql":
        return "sql_node"

    if route == "etl":
        return "etl_node"

    raise ValueError(f"Invalid route response: {route}")


# =========================================================
# BUILD LANGGRAPH
# =========================================================

builder = StateGraph(DataAgentSchema)

builder.add_node("router_node", router_node)
builder.add_node("etl_node", etl_node)
builder.add_node("sql_node", sql_node)

builder.add_edge(START, "router_node")

builder.add_conditional_edges(
    "router_node",
    route_edge,
    {
        "sql_node": "sql_node",
        "etl_node": "etl_node",
    },
)

builder.add_edge("sql_node", END)
builder.add_edge("etl_node", END)

data_agent = builder.compile()


# =========================================================
# OPTIONAL GRAPH VISUALIZATION
# =========================================================

def save_graph():
    try:
        graph_image = data_agent.get_graph().draw_mermaid_png()

        output_path = PROJECT_ROOT / "data_agent_graph.png"
        output_path.write_bytes(graph_image)

        print(f"Graph saved to: {output_path}")

    except Exception as exc:
        print(f"Graph visualization unavailable: {exc}")


# =========================================================
# RUN DATA AGENT
# =========================================================

if __name__ == "__main__":
    save_graph()

    user_request = (
        "Extract data from the API endpoint "
        "'https://pokeapi.co/api/v2/pokemon' and save it "
        "to the data/extract folder in CSV format."
    )

    try:
        response = data_agent.invoke(
            {
                "messages": [
                    HumanMessage(content=user_request)
                ],
                "route_response": "",
            },
            config={"recursion_limit": 40},
        )

        print("\n========== DATA AGENT RESPONSE ==========\n")

        messages = get_state_value(response, "messages", [])

        for message in messages:
            if isinstance(message, AIMessage) and message.content:
                print(message.content)

    except Exception as exc:
        print(
            f"Data agent failed: {type(exc).__name__}: {exc}"
        )
