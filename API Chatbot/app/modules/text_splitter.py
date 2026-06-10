from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.config import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP, get_setting


def split_documents(documents: list[Document]) -> list[Document]:
    """Split documents into chunks using RecursiveCharacterTextSplitter."""
    chunk_size = int(get_setting("chunk_size", str(DEFAULT_CHUNK_SIZE)))
    chunk_overlap = int(get_setting("chunk_overlap", str(DEFAULT_CHUNK_OVERLAP)))

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    split_docs = text_splitter.split_documents(documents)
    return split_docs
