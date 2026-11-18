"""Evolving Shared Memory: episodic lessons, salience decay, reinforcement, and superseding."""

from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class MemoryEntry:
    id: int
    topic: str
    lesson: str
    rationale: str
    salience: float
    access_count: int
    created_at: float
    last_accessed_at: float
    superseded_by: int | None = None


class EvolvingMemory:
    """SQLite-backed episodic memory that reinforces useful lessons and fades stale ones."""

    def __init__(self, db_path: str | Path = ":memory:", decay_half_life_days: float = 14.0) -> None:
        self.db_path = str(db_path)
        self.decay_lambda = math.log(2.0) / max(decay_half_life_days, 0.1)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                lesson TEXT NOT NULL,
                rationale TEXT NOT NULL,
                keywords TEXT NOT NULL,
                salience REAL NOT NULL DEFAULT 1.0,
                access_count INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                last_accessed_at REAL NOT NULL,
                superseded_by INTEGER DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS working_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                consolidated INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self.conn.commit()

    def log_turn(self, role: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO working_log (role, content, created_at, consolidated) VALUES (?, ?, ?, 0)",
            (role, content, time.time()),
        )
        self.conn.commit()

    def record_lesson(
        self,
        topic: str,
        lesson: str,
        rationale: str,
        *,
        keywords: list[str] | None = None,
        salience: float = 1.0,
        supersede_topic: bool = False,
        now: float | None = None,
    ) -> int:
        ts = now if now is not None else time.time()
        kw_list = sorted({w.lower() for w in (keywords or topic.split()) if len(w) > 1})
        cur = self.conn.execute(
            """
            INSERT INTO memories (topic, lesson, rationale, keywords, salience, access_count, created_at, last_accessed_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (topic, lesson, rationale, json.dumps(kw_list, ensure_ascii=False), salience, ts, ts),
        )
        new_id = int(cur.lastrowid)
        if supersede_topic:
            self.conn.execute(
                """
                UPDATE memories
                SET superseded_by = ?
                WHERE topic = ? AND id != ? AND superseded_by IS NULL
                """,
                (new_id, topic, new_id),
            )
        self.conn.commit()
        return new_id

    def effective_score(self, row: sqlite3.Row, query_terms: set[str], now: float) -> float:
        age_days = max(0.0, (now - float(row["last_accessed_at"])) / 86400.0)
        decay = math.exp(-self.decay_lambda * age_days)
        stored_kw = set(json.loads(row["keywords"]))
        topic_terms = {t.lower() for t in str(row["topic"]).replace("_", " ").split()}
        overlap = len(query_terms & (stored_kw | topic_terms))
        relevance = 1.0 + overlap * 0.75
        reinforcement = 1.0 + 0.15 * math.log1p(int(row["access_count"]))
        return float(row["salience"]) * decay * relevance * reinforcement

    def recall(self, query: str, *, limit: int = 3, min_score: float = 0.2, now: float | None = None) -> list[MemoryEntry]:
        ts = now if now is not None else time.time()
        query_terms = {t.lower() for t in query.replace("_", " ").split() if len(t) > 1}
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL"
        ).fetchall()

        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            score = self.effective_score(row, query_terms, ts)
            if score >= min_score:
                scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [row for _, row in scored[:limit]]

        entries: list[MemoryEntry] = []
        for row in selected:
            mem_id = int(row["id"])
            self.conn.execute(
                "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                (ts, mem_id),
            )
            entries.append(
                MemoryEntry(
                    id=mem_id,
                    topic=str(row["topic"]),
                    lesson=str(row["lesson"]),
                    rationale=str(row["rationale"]),
                    salience=float(row["salience"]),
                    access_count=int(row["access_count"]) + 1,
                    created_at=float(row["created_at"]),
                    last_accessed_at=ts,
                    superseded_by=row["superseded_by"],
                )
            )
        if selected:
            self.conn.commit()
        return entries

    def consolidate_sleep(self, *, now: float | None = None) -> int:
        """Idle-time consolidation: distills unconsolidated working logs into episodic memory."""
        ts = now if now is not None else time.time()
        rows = self.conn.execute(
            "SELECT id, role, content FROM working_log WHERE consolidated = 0 ORDER BY id ASC"
        ).fetchall()
        if not rows:
            return 0

        summary_snippets = [f"[{r['role']}] {str(r['content'])[:80]}" for r in rows[-4:]]
        self.record_lesson(
            topic="recent_collaboration",
            lesson=" | ".join(summary_snippets),
            rationale="Distilled during idle-time sleep consolidation",
            keywords=["collaboration", "session", "recent", "context"],
            salience=0.85,
            supersede_topic=True,
            now=ts,
        )
        ids = [(int(r["id"]),) for r in rows]
        self.conn.executemany("UPDATE working_log SET consolidated = 1 WHERE id = ?", ids)
        self.conn.commit()
        return len(rows)

    def close(self) -> None:
        self.conn.close()
