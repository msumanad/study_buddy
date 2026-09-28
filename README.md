# Study Buddy

Study Buddy is a Flask application for uploading course documents and answering subject-based questions with retrieval-augmented generation (RAG). PostgreSQL stores user accounts, Qdrant stores document chunks and vectors, Hugging Face creates embeddings locally, and Groq generates answers.

## Prerequisites

- Docker Engine with the Docker Compose plugin, or Docker Desktop with Compose
- Python 3.10 or newer
- A Groq API key with access to the model configured in `.env`
- Internet access the first time Hugging Face downloads the embedding model

The Flask application runs on the host. Docker Compose runs PostgreSQL and Qdrant.

## Setup and Run

Run these commands from the project directory.

### 1. Configure environment variables

Linux or WSL:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set a private `SECRET_KEY` and your Groq API key. The sample is configured for Groq and Hugging Face:

```dotenv
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=your-groq-api-key
EMBEDDINGS_PROVIDER=huggingface
EMBEDDINGS_MODEL=all-MiniLM-L6-v2
QDRANT_VECTOR_SIZE=384
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/study_buddy
QDRANT_URL=http://localhost:6333
```

Use a Groq model ID available to your account if the sample model is unavailable. Hugging Face downloads `all-MiniLM-L6-v2` on first use; its vectors have 384 dimensions, matching `QDRANT_VECTOR_SIZE`. Do not commit `.env` or share the API key.

### 2. Start PostgreSQL and Qdrant

```bash
docker compose up -d postgres qdrant
docker compose ps
```

The Compose file publishes PostgreSQL at `localhost:5432` and Qdrant at `localhost:6333`. Persistent Docker volumes keep their data between restarts.

### 3. Create a virtual environment and install packages

Linux or WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the application

```bash
python app.py
```

Open <http://localhost:5000>. On startup, the app creates the user table and seeds local default accounts if they do not already exist:

- Admin: `admin` / `admin123`
- User: `user` / `user123`

These defaults are for local development only. Change or remove them before exposing the application to other users.

## Add a User

With the virtual environment active and PostgreSQL running, open the Flask shell:

```bash
flask --app app shell
```

At the Python prompt, create a user. The password prompt hides typed input; `User.create_user` stores a password hash.

```python
from getpass import getpass
from app.models import User

username = input("Username: ").strip()
role = input("Role [user/admin]: ").strip() or "user"
User.create_user(username, getpass("Password: "), role)
```

Use `user` for regular question-answering accounts or `admin` for document-management access. Usernames must be unique.

## Architecture

```mermaid
flowchart LR
	Admin[Admin] -->|Upload PDF or DOCX| Flask[Flask application]
	Student[Student] -->|Ask question| Flask

	Flask -->|Accounts and authentication| Postgres[(PostgreSQL)]
	Flask -->|Original uploaded files| Uploads[Local uploads directory]

	Flask -->|Extract and split document| Ingest[Document ingestion]
	Ingest -->|Embed chunks| HF[Hugging Face embeddings]
	HF -->|Vectors and metadata| Qdrant[(Qdrant)]

	Flask -->|Embed question| HF
	HF -->|Subject-filtered similarity search| Qdrant
	Qdrant -->|Relevant chunks| Flask
	Flask -->|Question and retrieved context| Groq[Groq LLM]
	Groq -->|Answer| Flask
	Flask -->|Display answer| Student
```

PostgreSQL stores authentication data. Qdrant stores chunk text, vectors, and document metadata in a shared collection, with subject metadata used to filter retrieval. Original documents remain in the local `uploads/` directory.

## Request Sequence

```mermaid
sequenceDiagram
	actor Admin
	actor Student
	participant Flask as Flask application
	participant PostgreSQL
	participant HF as Hugging Face embeddings
	participant Qdrant
	participant Groq as Groq LLM

	Admin->>Flask: Upload document for a subject
	Flask->>PostgreSQL: Verify admin account
	Flask->>Flask: Save original file and split document
	loop For each chunk
		Flask->>HF: Embed chunk
		HF-->>Flask: Return vector
		Flask->>Qdrant: Store vector, text, and metadata
	end

	Student->>Flask: Submit question and subject
	Flask->>PostgreSQL: Verify user account
	Flask->>HF: Embed question
	HF-->>Flask: Return query vector
	Flask->>Qdrant: Search vectors filtered by subject
	Qdrant-->>Flask: Return relevant chunks
	Flask->>Groq: Generate answer from question and context
	Groq-->>Flask: Return answer
	Flask-->>Student: Display answer below question
```

## Common Commands

Stop the containers while preserving their data:

```bash
docker compose down
```

Stop containers and delete their persisted database and vector-store data:

```bash
docker compose down -v
```

The second command permanently deletes the PostgreSQL and Qdrant data volumes.
