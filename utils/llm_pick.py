from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

load_dotenv()

def pick_llm(level:str):
    """
    Picks the appropriate LLM basedn on the level of the question.

    Args:
        level (str):The level of the question ,can be "easy","medium",or "hard".
    Returns:
    str:The name of the llm to be used 
    """
    if level.lower()=="low":
        llm=ChatGroq(model_name="openai/gpt-oss-20b",temperature=0)
    elif level.lower()=="medium":
        llm =ChatGroq(model_name="openai/gpt-oss-120b",temperature=0)
    elif level.lower()=="high":
        llm=ChatGroq(model_name="qwen/qwen3.8-27b",temperature=0)
    elif level.lower()=="groq":
        llm=ChatGroq(model_name="qwen/qwen3.8-27b",temperature=0)
    else:
        raise ValueError(f"Unsupported level:{level}")
    return llm


# llm_obj=pick_llm("medium")
# print(llm_obj.invoke("what is the capital of India?"))