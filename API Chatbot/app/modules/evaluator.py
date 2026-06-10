import time
import json
from app.config import get_db_connection


def log_evaluation(question: str, answer: str, similarity_score: float,
                   response_time: float, source_documents: list[dict]):
    """Log evaluation result to database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO evaluations (question, answer, similarity_score, response_time, source_documents)
           VALUES (?, ?, ?, ?, ?)""",
        (question, answer, similarity_score, response_time, json.dumps(source_documents, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def calculate_similarity_score(source_documents: list) -> float:
    """Calculate average similarity score from retrieved documents.
    Uses document metadata if available, otherwise returns based on document count.
    """
    if not source_documents:
        return 0.0

    scores = []
    for doc in source_documents:
        if hasattr(doc, "metadata") and "score" in doc.metadata:
            scores.append(doc.metadata["score"])

    if scores:
        return sum(scores) / len(scores)

    # Heuristic: more source documents found = higher relevance likelihood
    return min(len(source_documents) / 4.0, 1.0)


def get_evaluation_history(limit: int = 50) -> list[dict]:
    """Get recent evaluation logs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM evaluations ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
