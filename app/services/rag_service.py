import os
import uuid
from typing import List

from langchain_community.document_loaders import UnstructuredWordDocumentLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LangChainDocument
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_openai import OpenAIEmbeddings, AzureOpenAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import OllamaEmbeddings
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from langchain_groq import ChatGroq

from app.config import Config


class RAGService:
    def __init__(self, app):
        self.app = app
        self.qdrant_client = self._build_qdrant_client()
        self._embeddings = None
        self.llm = self._build_llm()

    @property
    def embeddings(self):
        if self._embeddings is None:
            self._embeddings = self._build_embeddings()
        return self._embeddings

    def _build_qdrant_client(self):
        return QdrantClient(url=Config.QDRANT_URL, api_key=Config.QDRANT_API_KEY or None)

    def _build_embeddings(self):
        provider = Config.EMBEDDINGS_PROVIDER.lower()
        model = Config.EMBEDDINGS_MODEL

        if provider == "huggingface":
            return HuggingFaceEmbeddings(model_name=model)
        if provider == "openai":
            return OpenAIEmbeddings(model=model, api_key=Config.EMBEDDINGS_API_KEY)
        if provider == "azure":
            return AzureOpenAIEmbeddings(
                azure_endpoint=Config.EMBEDDINGS_ENDPOINT,
                api_key=Config.EMBEDDINGS_API_KEY,
                api_version=Config.EMBEDDINGS_API_VERSION,
                model=model,
            )
        if provider == "ollama":
            return OllamaEmbeddings(base_url=Config.EMBEDDINGS_ENDPOINT, model=model)
        raise ValueError(f"Unsupported embedding provider: {provider}")

    def _build_llm(self):
        provider = Config.LLM_PROVIDER.lower()
        model = Config.LLM_MODEL

        if provider == "groq":
            return ChatGroq(model=model, api_key=Config.LLM_API_KEY, temperature=0.3)
        if provider == "openai":
            return ChatOpenAI(model=model, api_key=Config.LLM_API_KEY, temperature=0)
        if provider == "azure":
            return AzureChatOpenAI(
                azure_endpoint=Config.LLM_ENDPOINT,
                api_key=Config.LLM_API_KEY,
                api_version=Config.LLM_API_VERSION,
                azure_deployment=model,
                temperature=0,
            )
        if provider == "ollama":
            return OllamaLLM(model=model, base_url=Config.LLM_ENDPOINT, temperature=0)
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

    def store_documents(self, chunks):
        collection_name = self._get_collection_name()
        self._ensure_collection(collection_name)
        vector_store = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=collection_name,
            embedding=self.embeddings,
        )

        vector_store.add_documents(chunks)
        return collection_name

    def retrieve_context(self, question: str, subject: str, k: int = None):
        collection_name = self._get_collection_name()
        if not self.qdrant_client.collection_exists(collection_name):
            return []

        vector_store = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=collection_name,
            embedding=self.embeddings,
        )
        limit = k if k is not None else Config.RAG_TOP_K
        subject_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="metadata.subject_key",
                    match=qdrant_models.MatchValue(value=self._subject_key(subject)),
                )
            ]
        )
        return vector_store.similarity_search(question, k=limit, filter=subject_filter)

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
        subject = " ".join(subject.split())
        subject_key = self._subject_key(subject)
        document_id = str(uuid.uuid4())
        storage_filename = os.path.basename(file_path)
        loaded_docs = self.load_documents(file_path)
        split_docs = self.split_documents(loaded_docs)

        metadata = {
            "document_id": document_id,
            "subject": subject,
            "subject_key": subject_key,
            "source_file": original_filename,
            "storage_filename": storage_filename,
            "uploaded_by": uploaded_by,
        }
        for doc in split_docs:
            doc.metadata.update(metadata)

        try:
            self.store_documents(split_docs)
        except Exception:
            self._delete_qdrant_document(document_id)
            raise

        return {
            "document_id": document_id,
            "filename": original_filename,
            "subject": subject,
            "storage_path": file_path,
            "uploaded_by": uploaded_by,
        }

    def delete_document(self, document_id: str):
        if not self.qdrant_client.collection_exists(self._get_collection_name()):
            return None

        document_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="metadata.document_id",
                    match=qdrant_models.MatchValue(value=document_id),
                )
            ]
        )
        point = next(self._scroll_points(scroll_filter=document_filter, limit=1), None)
        if point is None:
            return None

        metadata = self._point_metadata(point)
        storage_filename = metadata.get("storage_filename", "")
        self._delete_qdrant_document(document_id)
        return storage_filename

    def _delete_qdrant_document(self, document_id: str):
        collection_name = self._get_collection_name()
        if self.qdrant_client.collection_exists(collection_name):
            self.qdrant_client.delete(
                collection_name=collection_name,
                points_selector=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="metadata.document_id",
                            match=qdrant_models.MatchValue(value=document_id),
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
        collection = self.qdrant_client.get_collection(collection_name)
        if not collection.payload_schema or "metadata.subject_key" not in collection.payload_schema:
            self.qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="metadata.subject_key",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
            )

    def _get_collection_name(self):
        return f"{Config.VECTOR_COLLECTION_PREFIX}_documents"

    @staticmethod
    def _subject_key(subject: str):
        return " ".join(subject.split()).casefold()

    @staticmethod
    def _point_metadata(point):
        payload = point.payload or {}
        return payload.get("metadata", payload)

    def _scroll_points(self, scroll_filter=None, limit=1000):
        collection_name = self._get_collection_name()
        if not self.qdrant_client.collection_exists(collection_name):
            return

        offset = None
        while True:
            points, offset = self.qdrant_client.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            yield from points
            if offset is None:
                break

    def get_subjects(self):
        labels_by_key = {}
        for document in self.list_documents():
            subject = document["subject"]
            labels_by_key.setdefault(self._subject_key(subject), subject)
        return sorted(labels_by_key.values(), key=str.casefold)

    def list_documents(self, subject: str | None = None):
        scroll_filter = None
        if subject:
            scroll_filter = qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="metadata.subject_key",
                        match=qdrant_models.MatchValue(value=self._subject_key(subject)),
                    )
                ]
            )

        documents = {}
        for point in self._scroll_points(scroll_filter=scroll_filter):
            metadata = self._point_metadata(point)
            filename = metadata.get("source_file")
            if not filename:
                continue

            document_id = metadata.get("document_id")
            subject_name = metadata.get("subject", "")
            key = document_id or (filename, subject_name)
            documents.setdefault(
                key,
                {
                    "document_id": document_id,
                    "filename": filename,
                    "subject": subject_name,
                    "uploaded_by": metadata.get("uploaded_by"),
                },
            )

        return sorted(
            documents.values(),
            key=lambda document: (document["subject"].casefold(), document["filename"].casefold()),
        )
