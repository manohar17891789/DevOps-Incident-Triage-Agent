"""Chat model factory, kept as its own function so tests can monkeypatch it."""
from langchain_openai import ChatOpenAI

from config import settings


def get_chat_model(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(model=settings.openai_model, temperature=temperature, api_key=settings.openai_api_key)
