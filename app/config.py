import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/study_buddy")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}

    # Supported LLM providers: openai, azure, groq, ollama.
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
    LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_API_VERSION = os.getenv("LLM_API_VERSION", "2024-02-01")
    LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:11434")
    EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "openai")
    EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small")
    EMBEDDINGS_API_KEY = os.getenv("EMBEDDINGS_API_KEY", "")
    EMBEDDINGS_API_VERSION = os.getenv("EMBEDDINGS_API_VERSION", "2024-02-01")
    EMBEDDINGS_ENDPOINT = os.getenv("EMBEDDINGS_ENDPOINT", "http://localhost:11434")

    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
    VECTOR_COLLECTION_PREFIX = os.getenv("VECTOR_COLLECTION_PREFIX", "study_buddy")

    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
    QDRANT_VECTOR_SIZE = int(os.getenv("QDRANT_VECTOR_SIZE", "1536"))
    SYSTEM_PROMPT = os.getenv(
        "SYSTEM_PROMPT",
        "You are a helpful academic assistant. Answer using the retrieved course material. "
        "Put the direct answer first. Use plain text with short section headings on their own lines, "
        "and put each detail on its own line prefixed with '-'. Separate sections with a blank line. "
        "For profile questions, group supported details into relevant sections such as Summary, Experience, "
        "Skills, Education, Certifications, and Contact. If the answer is not available in the context, "
        "say so clearly and do not invent facts.",
    )

    DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    DEFAULT_USER_USERNAME = os.getenv("DEFAULT_USER_USERNAME", "user")
    DEFAULT_USER_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "user123")
