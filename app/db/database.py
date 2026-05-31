import sqlite3
import os
from app.config import Config

class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r") as f:
            schema = f.read()
        conn = self._connect()
        conn.executescript(schema)
        conn.commit()
        conn.close()

    def execute(self, query, params=()):
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        conn.commit()
        conn.close()
        return [dict(row) for row in rows]

    def fetchone(self, query, params=()):
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, params)
        row = cur.fetchone()
        conn.commit()
        conn.close()
        return dict(row) if row else None

    def fetchall(self, query, params=()):
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        conn.commit()
        conn.close()
        return [dict(row) for row in rows]
