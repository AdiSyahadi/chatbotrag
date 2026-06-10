import chromadb
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from app.config import VECTORSTORE_DIR, DEFAULT_TOP_K, get_setting
from app.modules.embedding import get_embedding


def save_to_vectorstore(docs: list[Document]):
    """Save document chunks to ChromaDB vectorstore."""
    embedding = get_embedding()
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embedding,
        persist_directory=VECTORSTORE_DIR,
    )
    return vectorstore


def get_retriever():
    """Get retriever from existing ChromaDB vectorstore."""
    embedding = get_embedding()
    top_k = int(get_setting("top_k", str(DEFAULT_TOP_K)))

    vectorstore = Chroma(
        persist_directory=VECTORSTORE_DIR,
        embedding_function=embedding,
    )
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": top_k},
    )
    return retriever


def get_vectorstore():
    """Get the raw ChromaDB vectorstore instance."""
    embedding = get_embedding()
    vectorstore = Chroma(
        persist_directory=VECTORSTORE_DIR,
        embedding_function=embedding,
    )
    return vectorstore


def delete_from_vectorstore(document_id: int) -> int:
    """Delete all chunks belonging to a document from ChromaDB vectorstore."""
    client = chromadb.PersistentClient(path=VECTORSTORE_DIR)
    collections = client.list_collections()

    total_deleted = 0
    for col in collections:
        results = col.get(where={"document_id": document_id})
        if results and results["ids"]:
            col.delete(ids=results["ids"])
            total_deleted += len(results["ids"])

    return total_deleted
