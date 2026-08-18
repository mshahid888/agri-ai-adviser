"""Feedback Loop and Analytics for M14 Agricultural AI Agent."""
from app.storage import save_feedback, DB_PATH
import sqlite3

def record_feedback(interaction_id: str, rating: int, comment: str):
    """Record farmer feedback."""
    if not (1 <= rating <= 5):
        raise ValueError("Rating must be between 1 and 5.")
    save_feedback(interaction_id, rating, comment)

def get_average_rating() -> float:
    """Aggregate average rating."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT AVG(rating) FROM feedback")
    avg = cursor.fetchone()[0]
    conn.close()
    return avg if avg else 0.0
