import os

os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-v1-test")
os.environ.setdefault("OPENROUTER_MODEL", "openrouter/free")
os.environ["TAVILY_API_KEY"] = ""
os.environ["SEARCHAPI_API_KEY"] = ""
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/research_agent")
