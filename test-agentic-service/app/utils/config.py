"""Configuration helpers for model and embedding clients."""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

try:
    from langfuse import Langfuse
except ModuleNotFoundError:  # pragma: no cover - optional dependency at runtime
    Langfuse = None

env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


def get_llm():
    return AzureChatOpenAI(
        openai_api_key=os.getenv("AOAI_API_KEY"),
        azure_endpoint=os.getenv("AOAI_ENDPOINT"),
        azure_deployment=os.getenv("AOAI_DEPLOY_GPT4O"),
        api_version=os.getenv("AOAI_API_VERSION"),
        temperature=0.2,
    )


def get_embeddings():
    return AzureOpenAIEmbeddings(
        model=os.getenv("AOAI_EMBEDDING_DEPLOYMENT"),
        openai_api_version=os.getenv("AOAI_API_VERSION"),
        api_key=os.getenv("AOAI_API_KEY"),
        azure_endpoint=os.getenv("AOAI_ENDPOINT"),
    )


def get_langfuse() -> Optional["Langfuse"]:
    if Langfuse is None:
        return None
    if not os.getenv("LANGFUSE_SECRET_KEY") or not os.getenv("LANGFUSE_PUBLIC_KEY"):
        return None
    return Langfuse(
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        host=os.getenv("LANGFUSE_HOST"),
    )


langfuse = get_langfuse()
