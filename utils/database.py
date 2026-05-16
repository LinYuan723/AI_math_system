import sqlite3
import os
import uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "math_system.db")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            class_name TEXT NOT NULL,
            student_no TEXT
        );

        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT,
            class_name TEXT NOT NULL,
            total_score REAL DEFAULT 100
        );

        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            question_no INTEGER,
            knowledge_point TEXT,
            score REAL,
            max_score REAL,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (exam_id) REFERENCES exams(id)
        );

        CREATE TABLE IF NOT EXISTS error_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            knowledge_point TEXT,
            question_text TEXT NOT NULL,
            student_answer TEXT,
            correct_answer TEXT,
            error_type TEXT,
            ai_analysis TEXT,
            source_type TEXT DEFAULT 'manual',
            exam_paper_id INTEGER,
            exam_paper_question_id INTEGER,
            image_path TEXT,
            error_count INTEGER DEFAULT 1,
            last_error_answer TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS exam_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exam_id) REFERENCES exams(id)
        );

        CREATE TABLE IF NOT EXISTS exam_paper_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER NOT NULL,
            question_no INTEGER,
            question_text TEXT NOT NULL,
            knowledge_point TEXT,
            correct_answer TEXT,
            question_type TEXT,
            FOREIGN KEY (paper_id) REFERENCES exam_papers(id)
        );

        CREATE TABLE IF NOT EXISTS class_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            question_text TEXT,
            knowledge_point TEXT
        );

        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id INTEGER,
            student_name TEXT,
            answer TEXT,
            is_correct INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES class_sessions(id)
        );
    """)

    # Migrate existing error_records table: add new columns if they don't exist
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(error_records)").fetchall()}
    new_columns = [
        ("source_type", "TEXT DEFAULT 'manual'"),
        ("exam_paper_id", "INTEGER"),
        ("exam_paper_question_id", "INTEGER"),
        ("image_path", "TEXT"),
        ("error_count", "INTEGER DEFAULT 1"),
        ("last_error_answer", "TEXT"),
    ]
    for col_name, col_def in new_columns:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE error_records ADD COLUMN {col_name} {col_def}")

    conn.commit()
    conn.close()


# --- Student operations ---

def add_student(name: str, class_name: str, student_no: str = "") -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO students (name, class_name, student_no) VALUES (?, ?, ?)",
        (name, class_name, student_no),
    )
    conn.commit()
    student_id = cursor.lastrowid
    conn.close()
    return student_id


def get_students(class_name: str = None) -> list:
    conn = get_connection()
    if class_name:
        rows = conn.execute("SELECT * FROM students WHERE class_name = ?", (class_name,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_by_name(name: str, class_name: str = None) -> dict | None:
    conn = get_connection()
    if class_name:
        row = conn.execute("SELECT * FROM students WHERE name = ? AND class_name = ?", (name, class_name)).fetchone()
    else:
        row = conn.execute("SELECT * FROM students WHERE name = ?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_or_create_student(name: str, class_name: str, student_no: str = "") -> int:
    student = get_student_by_name(name, class_name)
    if student:
        return student["id"]
    return add_student(name, class_name, student_no)


# --- Exam operations ---

def add_exam(name: str, class_name: str, date: str = None, total_score: float = 100) -> int:
    conn = get_connection()
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    cursor = conn.execute(
        "INSERT INTO exams (name, class_name, date, total_score) VALUES (?, ?, ?, ?)",
        (name, class_name, date, total_score),
    )
    conn.commit()
    exam_id = cursor.lastrowid
    conn.close()
    return exam_id


def get_exams(class_name: str = None) -> list:
    conn = get_connection()
    if class_name:
        rows = conn.execute("SELECT * FROM exams WHERE class_name = ? ORDER BY date DESC", (class_name,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM exams ORDER BY date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def exam_exists(exam_name: str, class_name: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM exams WHERE name = ? AND class_name = ?",
        (exam_name, class_name),
    ).fetchone()
    conn.close()
    return row["cnt"] > 0


def delete_exam(exam_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM scores WHERE exam_id = ?", (exam_id,))
    conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    conn.commit()
    conn.close()


# --- Score operations ---

def add_score(student_id: int, exam_id: int, question_no: int, knowledge_point: str, score: float, max_score: float):
    conn = get_connection()
    conn.execute(
        "INSERT INTO scores (student_id, exam_id, question_no, knowledge_point, score, max_score) VALUES (?, ?, ?, ?, ?, ?)",
        (student_id, exam_id, question_no, knowledge_point, score, max_score),
    )
    conn.commit()
    conn.close()


def get_scores_by_exam(exam_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT s.*, st.name as student_name, st.class_name "
        "FROM scores s JOIN students st ON s.student_id = st.id "
        "WHERE s.exam_id = ?",
        (exam_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scores_by_student(student_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT s.*, e.name as exam_name, e.date as exam_date "
        "FROM scores s JOIN exams e ON s.exam_id = e.id "
        "WHERE s.student_id = ? ORDER BY e.date",
        (student_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Error record operations ---

def add_error_record(student_id: int, question_text: str, student_answer: str,
                     correct_answer: str, knowledge_point: str = "", error_type: str = "", ai_analysis: str = "",
                     source_type: str = "manual", exam_paper_id: int = None, exam_paper_question_id: int = None,
                     image_path: str = "") -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO error_records (student_id, knowledge_point, question_text, student_answer, correct_answer, "
        "error_type, ai_analysis, source_type, exam_paper_id, exam_paper_question_id, image_path) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (student_id, knowledge_point, question_text, student_answer, correct_answer,
         error_type, ai_analysis, source_type, exam_paper_id, exam_paper_question_id, image_path),
    )
    conn.commit()
    record_id = cursor.lastrowid
    conn.close()
    return record_id


def find_duplicate_error(student_id: int, question_text: str, similarity_threshold: float = 0.8) -> dict | None:
    """Find an existing error record for the same student with similar question text.
    Uses a simple string similarity: checks if the new question is a substring of existing (or vice versa),
    or if they share a large portion of characters.
    Returns the matching record or None.
    """
    if not student_id or not question_text:
        return None
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM error_records WHERE student_id = ? ORDER BY created_at DESC LIMIT 50",
        (student_id,),
    ).fetchall()
    conn.close()

    new_text = question_text.strip()
    new_chars = set(new_text)

    for row in rows:
        existing = dict(row)
        existing_text = existing.get("question_text", "").strip()
        if not existing_text:
            continue

        # Fast check: exact or near-exact match
        if new_text == existing_text:
            return existing

        # Substring check
        if new_text in existing_text or existing_text in new_text:
            return existing

        # Character overlap ratio (simple similarity)
        existing_chars = set(existing_text)
        if len(new_chars) > 0 and len(existing_chars) > 0:
            overlap = len(new_chars & existing_chars)
            union = len(new_chars | existing_chars)
            similarity = overlap / union if union > 0 else 0
            if similarity >= similarity_threshold:
                return existing

    return None


def increment_error_count(record_id: int, new_answer: str = ""):
    """Increment the error_count of an existing record and update last_error_answer."""
    conn = get_connection()
    conn.execute(
        "UPDATE error_records SET error_count = error_count + 1, last_error_answer = ?, "
        "created_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_answer, record_id),
    )
    conn.commit()
    conn.close()


def delete_error_record(record_id: int):
    """Delete an error record by ID."""
    conn = get_connection()
    conn.execute("DELETE FROM error_records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def get_error_records(student_id: int = None, knowledge_point: str = None) -> list:
    conn = get_connection()
    query = "SELECT er.*, st.name as student_name FROM error_records er LEFT JOIN students st ON er.student_id = st.id WHERE 1=1"
    params = []
    if student_id:
        query += " AND er.student_id = ?"
        params.append(student_id)
    if knowledge_point:
        query += " AND er.knowledge_point = ?"
        params.append(knowledge_point)
    query += " ORDER BY er.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Classroom session operations ---

def add_session(name: str, question_text: str = "", knowledge_point: str = "") -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO class_sessions (name, question_text, knowledge_point) VALUES (?, ?, ?)",
        (name, question_text, knowledge_point),
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return session_id


def get_sessions() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM class_sessions ORDER BY date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_response(session_id: int, student_name: str, answer: str, is_correct: bool, student_id: int = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO responses (session_id, student_id, student_name, answer, is_correct) VALUES (?, ?, ?, ?, ?)",
        (session_id, student_id, student_name, answer, 1 if is_correct else 0),
    )
    conn.commit()
    conn.close()


def get_responses(session_id: int) -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM responses WHERE session_id = ?", (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Exam paper operations ---

def add_exam_paper(exam_id: int, image_path: str) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO exam_papers (exam_id, image_path) VALUES (?, ?)",
        (exam_id, image_path),
    )
    conn.commit()
    paper_id = cursor.lastrowid
    conn.close()
    return paper_id


def get_exam_papers(exam_id: int = None) -> list:
    conn = get_connection()
    if exam_id:
        rows = conn.execute(
            "SELECT ep.*, e.name as exam_name FROM exam_papers ep "
            "JOIN exams e ON ep.exam_id = e.id WHERE ep.exam_id = ? ORDER BY ep.created_at DESC",
            (exam_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT ep.*, e.name as exam_name FROM exam_papers ep "
            "JOIN exams e ON ep.exam_id = e.id ORDER BY ep.created_at DESC",
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_exam_paper_by_exam(exam_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM exam_papers WHERE exam_id = ? ORDER BY created_at DESC LIMIT 1",
        (exam_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Exam paper question operations ---

def add_exam_paper_question(paper_id: int, question_text: str, question_no: int = None,
                            knowledge_point: str = "", correct_answer: str = "", question_type: str = "") -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO exam_paper_questions (paper_id, question_no, question_text, knowledge_point, correct_answer, question_type) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (paper_id, question_no, question_text, knowledge_point, correct_answer, question_type),
    )
    conn.commit()
    q_id = cursor.lastrowid
    conn.close()
    return q_id


def add_exam_paper_questions_batch(paper_id: int, questions: list[dict]) -> list[int]:
    """Batch insert exam paper questions. Each dict: {question_no, question_text, knowledge_point, correct_answer, question_type}"""
    conn = get_connection()
    ids = []
    for q in questions:
        cursor = conn.execute(
            "INSERT INTO exam_paper_questions (paper_id, question_no, question_text, knowledge_point, correct_answer, question_type) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (paper_id, q.get("question_no"), q.get("question_text", ""),
             q.get("knowledge_point", ""), q.get("correct_answer", ""), q.get("question_type", "")),
        )
        ids.append(cursor.lastrowid)
    conn.commit()
    conn.close()
    return ids


def get_exam_paper_questions(paper_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM exam_paper_questions WHERE paper_id = ? ORDER BY question_no",
        (paper_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_exam_paper_questions(paper_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM exam_paper_questions WHERE paper_id = ?", (paper_id,))
    conn.commit()
    conn.close()


# --- File upload utility ---

def save_upload_file(uploaded_file, prefix: str = "upload") -> str:
    """Save a Streamlit UploadedFile to the uploads directory. Returns the saved file path."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(uploaded_file.name)[1] or ".png"
    filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


# --- Review reminder operations ---

def get_error_records_needing_review(student_id: int = None, days_since_last_review: int = 1) -> list:
    """Get error records that need review based on time elapsed since creation."""
    conn = get_connection()
    query = (
        "SELECT er.*, st.name as student_name FROM error_records er "
        "LEFT JOIN students st ON er.student_id = st.id WHERE 1=1"
    )
    params = []
    if student_id:
        query += " AND er.student_id = ?"
        params.append(student_id)
    query += " AND DATE(er.created_at) <= DATE('now', ?)"
    params.append(f"-{days_since_last_review} days")
    query += " ORDER BY er.created_at ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize database on import
init_db()
