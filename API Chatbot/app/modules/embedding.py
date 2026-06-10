from langchain_huggingface import HuggingFaceEmbeddings


def get_embedding():
    """Initialize local HuggingFace embedding model (gratis, tanpa API key)."""
    embedding = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
    )
    return embedding
