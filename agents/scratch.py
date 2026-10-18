


import os
import sys

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
)

from utils.llm_pick import pick_llm
from utils.database import DatabaseUtil
from models.schema import AgentSchema, JudgeSchema

llm = pick_llm("medium")
llm_judge = llm.with_structured_output(JudgeSchema)

sql_query = "SELECT * FROM users WHERE age > 30;"

prompt = f"""You are an SQL JUDGE for security.
Your task is to determine whether the SQL query is safe.

The query must only retrieve data and must not modify the
database structure or content.

Reject queries containing INSERT, UPDATE, DELETE, DROP,
ALTER, TRUNCATE, CREATE, or other data-modifying commands.

If safe, return 'Yes'; otherwise, return 'No'.
Provide comments explaining your decision.

SQL query to evaluate:
{sql_query}
"""

result = llm_judge.invoke(prompt).model_dump()
print(result)





