import os
from typing import List

from langchain_community.document_loaders import UnstructuredWordDocumentLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LangChainDocument
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_openai import OpenAIEmbeddings, AzureOpenAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import Qdrant
from langchain_community.embeddings import OllamaEmbeddings
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from langchain_groq import ChatGroq

from app import db
from app.config import Config


class RAGService:
    def __init__(self, app):
        self.app = app
        self.qdrant_client = self._build_qdrant_client()
        self.embeddings = self._build_embeddings()
        #self.llm = self._build_llm()

    def _build_qdrant_client(self):
        return QdrantClient(url=Config.QDRANT_URL, api_key=Config.QDRANT_API_KEY or None)

    def _build_embeddings(self):
        provider = Config.EMBEDDINGS_PROVIDER.lower()
        model = Config.EMBEDDINGS_MODEL

        if provider == "huggingface":
            return HuggingFaceEmbeddings(model_name=model)
        if provider == "openai":
            return OpenAIEmbeddings(model=model, api_key=Config.OPENAI_API_KEY)
        if provider == "azure":
            return AzureOpenAIEmbeddings(
                azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                api_key=Config.AZURE_OPENAI_API_KEY,
                api_version=Config.AZURE_OPENAI_API_VERSION,
                model=model,
            )
        if provider == "ollama":
            return OllamaEmbeddings(base_url=Config.OLLAMA_BASE_URL, model=model)
        raise ValueError(f"Unsupported embedding provider: {provider}")

    def _build_llm(self):
        provider = Config.LLM_PROVIDER.lower()
        model = Config.LLM_MODEL

        if provider == "groq":
            return ChatGroq(model=modl, api_key=Config.GROQ_API_KEY, temperature=0.3)
        if provider == "openai":
            return ChatOpenAI(model=model, api_key=Config.OPENAI_API_KEY, temperature=0)
        if provider == "azure":
            return AzureChatOpenAI(
                azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                api_key=Config.AZURE_OPENAI_API_KEY,
                api_version=Config.AZURE_OPENAI_API_VERSION,
                azure_deployment=model,
                temperature=0,
            )
        if provider == "ollama":
            return OllamaLLM(model=model, base_url=Config.OLLAMA_BASE_URL, temperature=0)
        raise ValueError(f"Unsupported LLM provider: {provider}")

    def load_documents(self, file_path: str):
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
            return loader.load()
        if ext in {".doc", ".docx"}:
            loader = UnstructuredWordDocumentLoader(file_path)
            return loader.load()
        raise ValueError("Unsupported file type")

    def split_documents(self, documents: List[LangChainDocument]):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_documents(documents)

    def embed_documents(self, texts: List[str]):
        return self.embeddings.embed_documents(texts)

    def store_documents(self, chunks, subject: str):
        collection_name = self._get_collection_name(subject)
        self._ensure_collection(collection_name)
        vector_store = Qdrant(
            client=self.qdrant_client,
            collection_name=collection_name,
            embeddings=self.embeddings,
        )

        vector_store.add_documents(chunks)
        return collection_name

    def retrieve_context(self, question: str, subject: str, k: int = None):
        collection_name = self._get_collection_name(subject)
        if not self.qdrant_client.collection_exists(collection_name):
            return []

        vector_store = Qdrant(
            client=self.qdrant_client,
            collection_name=collection_name,
            embeddings=self.embeddings,
        )
        limit = k if k is not None else Config.RAG_TOP_K
        return vector_store.similarity_search(question, k=limit)

    def build_rag_chain(self, subject: str, k: int = None):
        limit = k if k is not None else Config.RAG_TOP_K
        retriever = RunnableLambda(lambda question: self.retrieve_context(question, subject, k=limit))

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", Config.SYSTEM_PROMPT),
                ("human", "Question: {question}\n\nRelevant context:\n{context}"),
            ]
        )

        chain = (
            RunnableParallel(
                question=RunnablePassthrough(),
                context=retriever | RunnableLambda(lambda docs: "\n\n".join(doc.page_content for doc in docs)),
            )
            | prompt
            | self.llm
            | StrOutputParser()
        )
        return chain

    def answer_question(self, question: str, subject: str):
        chain = self.build_rag_chain(subject=subject, k=Config.RAG_TOP_K)
        return chain.invoke(question)

    def ingest_document(self, file_path: str, subject: str, original_filename: str, uploaded_by: int):
        loaded_docs = self.load_documents(file_path)
        split_docs = self.split_documents(loaded_docs)

        metadata = {"subject": subject, "source_file": original_filename, "uploaded_by": uploaded_by}
        for doc in split_docs:
            doc.metadata.update(metadata)

        # Store document content and metadata in Qdrant only. We save a minimal registry
        # in the filesystem (storage path) but do not persist a SQL record.
        self.store_documents(split_docs, subject)
        # Return a lightweight dict to indicate success
        return {
            "filename": original_filename,
            "subject": subject,
            "storage_path": file_path,
            "uploaded_by": uploaded_by,
        }

    def delete_document(self, filename: str, subject: str):
        collection_name = self._get_collection_name(subject)
        if self.qdrant_client.collection_exists(collection_name):
            self.qdrant_client.delete(
                collection_name=collection_name,
                points_selector=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="source_file",
                            match=qdrant_models.MatchValue(value=filename),
                        )
                    ]
                ),
            )

    def _ensure_collection(self, collection_name: str):
        if not self.qdrant_client.collection_exists(collection_name):
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=Config.QDRANT_VECTOR_SIZE,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )

    def _get_collection_name(self, subject: str):
        return f"{Config.VECTOR_COLLECTION_PREFIX}_{subject.lower().replace(' ', '_')}"
    def get_subjects(self):
        # List Qdrant collections and extract subject names by prefix
        try:
            all_collections = [c.name for c in self.qdrant_client.get_collections().collections]
        except Exception:
            return []
        prefix = f"{Config.VECTOR_COLLECTION_PREFIX}_"
        subjects = []
        for name in all_collections:
            if name.startswith(prefix):
                subj = name[len(prefix) :].replace("_", " ")
                subjects.append(subj)
        return sorted(subjects)

    def list_documents(self, subject: str | None = None):
        # Return a list of uploaded documents (filename + subject + uploaded_by) by scanning collections
        prefix = f"{Config.VECTOR_COLLECTION_PREFIX}_"
        collections = []
        try:
            all_collections = [c.name for c in self.qdrant_client.get_collections().collections]
        except Exception:
            return []

        if subject:
            coll_name = self._get_collection_name(subject)
            if coll_name in all_collections:
                collections = [coll_name]
            else:
                return []
        else:
            collections = [name for name in all_collections if name.startswith(prefix)]

        docs = []
        seen = set()
        for coll in collections:
            try:
                resp = self.qdrant_client.scroll(collection_name=coll, limit=1000)
                points = getattr(resp, "points", None) or getattr(resp, "result", None) or resp
                # points may be a list of point objects or dicts
                for p in points:
                    payload = getattr(p, "payload", None) or p.get("payload", {}) if isinstance(p, dict) else {}
                    filename = payload.get("source_file")
                    if not filename:
                        continue
                    key = (coll, filename)
                    if key in seen:
                        continue
                    seen.add(key)
                    subj = coll[len(prefix) :].replace("_", " ")
                    docs.append({
                        "filename": filename,
                        "subject": subj,
                        "uploaded_by": payload.get("uploaded_by"),
                    })
            except Exception:
                continue

        return docs
