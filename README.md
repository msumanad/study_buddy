# Study Buddy

AI Buddy for students with role-based access, document ingestion, and a configurable RAG pipeline using LangChain, Qdrant, and PostgreSQL.

## Features

- Admin login for uploading and deleting documents
- Regular user login for subject-based question answering
- PDF and DOC/DOCX upload support
- Document loading, chunking, embedding, vector storage, and retrieval using LangChain + Qdrant
- Postgres for auth and app metadata only
- Configurable LLM and embedding providers via environment variables
- LCEL-based retrieval chain with system prompt support

## Prerequisites

Before starting, make sure you have:

- Python 3.10+
- PostgreSQL running locally or via Docker
- Qdrant running locally or via Docker
- An API key for the configured LLM provider if using OpenAI/Azure OpenAI

## 1) Clone and open the project

```bash
cd /path/to/study_buddy
```

## 2) Create the environment file

Copy the sample environment file and update the values:

```bash
cp .env.example .env
```

Then edit `.env` and set the required values such as:

```env
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/study_buddy
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
EMBEDDINGS_PROVIDER=openai
EMBEDDINGS_MODEL=text-embedding-3-small
OPENAI_API_KEY=your-openai-api-key
UPLOAD_FOLDER=uploads
ALLOWED_EXTENSIONS=.pdf,.doc,.docx
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=admin123
DEFAULT_USER_USERNAME=user
DEFAULT_USER_PASSWORD=user123
```

If you use Ollama instead of OpenAI, set:

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1
EMBEDDINGS_PROVIDER=ollama
EMBEDDINGS_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434
```

## 3) Start PostgreSQL and Qdrant

This project includes a Docker Compose file for local services.

```bash
docker compose up -d
```

This starts:

- PostgreSQL on `localhost:5432`
- Qdrant on `localhost:6333`

## 4) Create a Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 5) Install dependencies

```bash
pip install -r requirements.txt
```

## 6) Run database initialization

The app auto-creates tables on startup and seeds default users.

## 7) Start the Flask app

```bash
python app.py
```

Or:

```bash
flask --app app run --debug
```

Then open:

```text
http://localhost:5000
```

## Default login users

- Admin: `admin` / `admin123`
- User: `user` / `user123`

## How the app works

1. Admin logs in.
2. Admin uploads a PDF or DOC/DOCX file for a subject.
3. The file is loaded, chunked, embedded, and stored in Qdrant.
4. User logs in and selects a subject.
5. User asks a question.
6. The query is embedded and compared against the subject collection in Qdrant.
7. Relevant chunks are retrieved and passed into the LLM with a system prompt.
8. The LLM answers based on the retrieved context.

## Notes

- The document files are kept in the local upload folder and metadata registered in Postgres.
- The actual document content used for retrieval lives in Qdrant.
- The model/provider settings are controlled in `.env` for easy switching between OpenAI, Azure OpenAI, and Ollama.
