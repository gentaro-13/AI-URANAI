import sqlite3, pathlib, datetime

DB_PATH = pathlib.Path("chatlog.db")

def _conn():
    """データベース接続を確立し、必要なテーブルを作成"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # チャットログテーブル
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            user_id TEXT,
            role TEXT,
            text TEXT,
            timestamp TEXT
        )
    """)
    
    # ユーザープロファイルテーブル
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            gender TEXT,
            birthdate TEXT,
            updated_at TEXT
        )
    """)
    
    conn.commit()
    return conn

def save_msg(user_id: str, role: str, text: str, timestamp: str = None):
    """メッセージを保存"""
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    
    with _conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO logs (user_id, role, text, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, role, text, timestamp)
        )

def save_profile(user_id: str, gender: str = None, birthdate: str = None):
    """ユーザープロファイルを保存または更新"""
    with _conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO user_profiles (user_id, gender, birthdate, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                gender = COALESCE(?, gender),
                birthdate = COALESCE(?, birthdate),
                updated_at = ?
            """,
            (
                user_id, gender, birthdate, datetime.now().isoformat(),
                gender, birthdate, datetime.now().isoformat()
            )
        )

def fetch_recent(user_id: str, limit: int = 10):
    """最近のメッセージを取得"""
    with _conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        )
        return c.fetchall()

def get_profile(user_id: str):
    """ユーザープロファイルを取得"""
    with _conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,)
        )
        return c.fetchone() 