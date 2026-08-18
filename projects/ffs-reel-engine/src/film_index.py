from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_fingerprint(path: Path) -> str:
    """Fingerprint a large movie without hashing the entire feature."""
    stat = path.stat()
    digest = hashlib.sha256()
    digest.update(str(stat.st_size).encode())
    digest.update(str(stat.st_mtime_ns).encode())
    with path.open("rb") as source:
        digest.update(source.read(1024 * 1024))
        if stat.st_size > 1024 * 1024:
            source.seek(max(0, stat.st_size - 1024 * 1024))
            digest.update(source.read(1024 * 1024))
    return digest.hexdigest()


class FilmIndex:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shots (
                    id INTEGER PRIMARY KEY,
                    start REAL NOT NULL,
                    end REAL NOT NULL,
                    duration REAL NOT NULL,
                    scene_score_threshold REAL,
                    representative_time REAL NOT NULL,
                    thumbnail TEXT,
                    selected_for_browser INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(start, end)
                );
                CREATE TABLE IF NOT EXISTS transcript_segments (
                    id INTEGER PRIMARY KEY,
                    start REAL NOT NULL,
                    end REAL NOT NULL,
                    text TEXT NOT NULL,
                    speaker TEXT,
                    confidence REAL
                );
                CREATE TABLE IF NOT EXISTS transcript_words (
                    id INTEGER PRIMARY KEY,
                    start REAL NOT NULL,
                    end REAL NOT NULL,
                    text TEXT NOT NULL,
                    confidence REAL,
                    source TEXT NOT NULL DEFAULT 'full_transcript',
                    UNIQUE(start, end, text)
                );
                CREATE INDEX IF NOT EXISTS transcript_words_time
                    ON transcript_words(start, end);
                CREATE TABLE IF NOT EXISTS normalized_transcript (
                    id INTEGER PRIMARY KEY,
                    start REAL NOT NULL,
                    end REAL NOT NULL,
                    text TEXT NOT NULL,
                    source_ids_json TEXT NOT NULL DEFAULT '[]',
                    flags_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS scenes (
                    id INTEGER PRIMARY KEY,
                    start REAL NOT NULL,
                    end REAL NOT NULL,
                    title TEXT,
                    summary TEXT,
                    review_status TEXT NOT NULL DEFAULT 'unreviewed',
                    boundary_score REAL,
                    boundary_reasons_json TEXT NOT NULL DEFAULT '[]',
                    dialogue_excerpt TEXT
                );
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY,
                    scene_id INTEGER,
                    kind TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    confidence REAL,
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    review_status TEXT NOT NULL DEFAULT 'needs_review',
                    FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS scene_documents (
                    scene_id INTEGER PRIMARY KEY,
                    transcript TEXT NOT NULL,
                    first_dialogue REAL,
                    last_dialogue REAL,
                    dialogue_seconds REAL NOT NULL DEFAULT 0,
                    dialogue_density REAL NOT NULL DEFAULT 0,
                    longest_silence REAL NOT NULL DEFAULT 0,
                    dialogue_units INTEGER NOT NULL DEFAULT 0,
                    question_count INTEGER NOT NULL DEFAULT 0,
                    keywords_json TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS scene_fts USING fts5(
                    scene_id UNINDEXED, title, transcript
                );
                CREATE TABLE IF NOT EXISTS semantic_passages (
                    id INTEGER PRIMARY KEY,
                    scene_id INTEGER NOT NULL,
                    start REAL NOT NULL,
                    end REAL NOT NULL,
                    text TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS semantic_passages_scene_id
                    ON semantic_passages(scene_id);
                """
            )
            existing_scene_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(scenes)")
            }
            for name, definition in {
                "boundary_score": "REAL",
                "boundary_reasons_json": "TEXT NOT NULL DEFAULT '[]'",
                "dialogue_excerpt": "TEXT",
            }.items():
                if name not in existing_scene_columns:
                    db.execute(f"ALTER TABLE scenes ADD COLUMN {name} {definition}")
            self.set_metadata({"schema_version": SCHEMA_VERSION, "updated_at": utc_now()}, db=db)

    def set_metadata(self, values: dict, *, db: sqlite3.Connection | None = None) -> None:
        def write(connection: sqlite3.Connection) -> None:
            connection.executemany(
                "INSERT INTO metadata(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                [(key, json.dumps(value)) for key, value in values.items()],
            )

        if db is not None:
            write(db)
        else:
            with self.connect() as connection:
                write(connection)

    def reset_for_source(self) -> None:
        """Atomically remove every layer derived from a previously loaded movie."""
        with self.connect() as db:
            # Keep the explicit order even though the relational tables also use
            # cascading foreign keys. The FTS table is independent, and clearing
            # every layer in one transaction prevents a half-old/half-new index.
            db.execute("DELETE FROM semantic_passages")
            db.execute("DELETE FROM observations")
            db.execute("DELETE FROM scene_documents")
            db.execute("DELETE FROM scene_fts")
            db.execute("DELETE FROM scenes")
            db.execute("DELETE FROM normalized_transcript")
            db.execute("DELETE FROM transcript_words")
            db.execute("DELETE FROM transcript_segments")
            db.execute("DELETE FROM shots")
            db.execute("DELETE FROM metadata")
            self.set_metadata({
                "schema_version": SCHEMA_VERSION,
                "shot_index_status": "pending",
                "transcript_status": "pending",
                "scene_index_status": "pending",
                "semantic_index_status": "pending",
                "updated_at": utc_now(),
            }, db=db)

    def semantic_index_signature(self) -> str:
        """Return a stable content signature for the current semantic index."""
        digest = hashlib.sha256(b"ffs-semantic-index-v1\0")

        def add(value: object) -> None:
            if isinstance(value, bytes):
                encoded = value
            else:
                encoded = str(value).encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)

        with self.connect() as db:
            metadata = {
                row["key"]: json.loads(row["value"])
                for row in db.execute(
                    "SELECT key,value FROM metadata WHERE key IN "
                    "('semantic_model','semantic_dimensions') ORDER BY key"
                )
            }
            add(metadata.get("semantic_model", ""))
            add(metadata.get("semantic_dimensions", ""))
            for row in db.execute(
                "SELECT id,scene_id,start,end,text,embedding "
                "FROM semantic_passages ORDER BY id"
            ):
                add(row["id"])
                add(row["scene_id"])
                add(format(float(row["start"]), ".9f"))
                add(format(float(row["end"]), ".9f"))
                add(row["text"])
                add(bytes(row["embedding"]))
        return digest.hexdigest()

    def replace_shots(self, shots: list[dict], threshold: float, browser_starts: set[float]) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM shots")
            db.executemany(
                """INSERT INTO shots
                (start,end,duration,scene_score_threshold,representative_time,selected_for_browser)
                VALUES(?,?,?,?,?,?)""",
                [
                    (
                        shot["start"], shot["end"], shot["shot_duration"], threshold,
                        shot["start"] + min(max(0.2, shot["shot_duration"] * 0.45), 1.5),
                        int(round(shot["start"], 3) in browser_starts),
                    )
                    for shot in shots
                ],
            )
            self.set_metadata(
                {"shot_index_status": "complete", "shot_count": len(shots), "updated_at": utc_now()},
                db=db,
            )

    def append_transcript(self, segments: list[dict], completed_through: float,
                          words: list[dict] | None = None) -> None:
        with self.connect() as db:
            db.executemany(
                """INSERT INTO transcript_segments(start,end,text,speaker,confidence)
                VALUES(?,?,?,?,?)""",
                [
                    (segment["start"], segment["end"], segment["text"],
                     segment.get("speaker"), segment.get("confidence"))
                    for segment in segments
                ],
            )
            if words:
                db.executemany(
                    """INSERT OR IGNORE INTO transcript_words
                    (start,end,text,confidence,source) VALUES(?,?,?,?,?)""",
                    [
                        (word["start"], word["end"], word["text"],
                         word.get("confidence"), word.get("source", "full_transcript"))
                        for word in words
                    ],
                )
            self.set_metadata(
                {"transcript_status": "running", "transcript_completed_through": completed_through,
                 "transcript_word_count": db.execute(
                     "SELECT COUNT(*) FROM transcript_words"
                 ).fetchone()[0],
                 "updated_at": utc_now()}, db=db,
            )

    def add_transcript_words(self, words: list[dict], *, source: str) -> int:
        if not words:
            return 0
        with self.connect() as db:
            before = db.execute("SELECT COUNT(*) FROM transcript_words").fetchone()[0]
            db.executemany(
                """INSERT OR IGNORE INTO transcript_words
                (start,end,text,confidence,source) VALUES(?,?,?,?,?)""",
                [(word["start"], word["end"], word["text"], word.get("confidence"), source)
                 for word in words],
            )
            after = db.execute("SELECT COUNT(*) FROM transcript_words").fetchone()[0]
            self.set_metadata({"transcript_word_count": after, "updated_at": utc_now()}, db=db)
            return int(after - before)

    def transcript_words(self, start: float | None = None,
                         end: float | None = None) -> list[dict]:
        query = "SELECT id,start,end,text,confidence,source FROM transcript_words"
        parameters: tuple = ()
        if start is not None and end is not None:
            query += " WHERE start < ? AND end > ?"
            parameters = (float(end), float(start))
        query += " ORDER BY start,id"
        with self.connect() as db:
            return [dict(row) for row in db.execute(query, parameters)]

    def reset_transcript(self) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM transcript_words")
            db.execute("DELETE FROM transcript_segments")
            self.set_metadata(
                {"transcript_status": "pending", "transcript_completed_through": 0.0,
                 "updated_at": utc_now()}, db=db,
            )

    def transcript_completed_through(self) -> float:
        return float(self.stats()["metadata"].get("transcript_completed_through", 0.0))

    def set_transcript_status(self, status: str, **extra) -> None:
        self.set_metadata({"transcript_status": status, "updated_at": utc_now(), **extra})

    def raw_transcript(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,start,end,text,speaker,confidence FROM transcript_segments ORDER BY start,id"
            )]

    def shots(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,start,end,duration,representative_time FROM shots ORDER BY start,id"
            )]

    def replace_normalized_transcript(self, segments: list[dict]) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM normalized_transcript")
            db.executemany(
                """INSERT INTO normalized_transcript
                (start,end,text,source_ids_json,flags_json) VALUES(?,?,?,?,?)""",
                [(s["start"], s["end"], s["text"], json.dumps(s.get("source_ids", [])),
                  json.dumps(s.get("flags", []))) for s in segments],
            )
            self.set_metadata({"normalized_transcript_status": "complete",
                               "normalized_transcript_count": len(segments),
                               "updated_at": utc_now()}, db=db)

    def normalized_transcript(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,start,end,text,source_ids_json,flags_json "
                "FROM normalized_transcript ORDER BY start,id"
            )]

    def replace_scenes(self, scenes: list[dict]) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM observations")
            db.execute("DELETE FROM scenes")
            db.executemany(
                """INSERT INTO scenes
                (start,end,title,summary,review_status,boundary_score,boundary_reasons_json,dialogue_excerpt)
                VALUES(?,?,?,?,?,?,?,?)""",
                [(s["start"], s["end"], s["title"], s.get("summary", ""), "unreviewed",
                  s.get("boundary_score"), json.dumps(s.get("boundary_reasons", [])),
                  s.get("dialogue_excerpt", "")) for s in scenes],
            )
            self.set_metadata({"scene_index_status": "proposed", "scene_count": len(scenes),
                               "updated_at": utc_now()}, db=db)

    def scenes(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT s.id,s.start,s.end,s.title,s.summary,s.review_status,s.boundary_score,
                s.boundary_reasons_json,s.dialogue_excerpt,d.first_dialogue,d.last_dialogue,
                d.dialogue_density,d.longest_silence,d.keywords_json
                FROM scenes s LEFT JOIN scene_documents d ON d.scene_id=s.id ORDER BY s.start,s.id"""
            )
            result = []
            for row in rows:
                item = dict(row)
                item["boundary_reasons"] = json.loads(item.pop("boundary_reasons_json"))
                item["keywords"] = json.loads(item.pop("keywords_json") or "[]")
                item["duration"] = item["end"] - item["start"]
                result.append(item)
            return result

    def replace_scene_documents(self, documents: list[dict]) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM scene_documents")
            db.execute("DELETE FROM scene_fts")
            db.executemany(
                """INSERT INTO scene_documents
                (scene_id,transcript,first_dialogue,last_dialogue,dialogue_seconds,
                 dialogue_density,longest_silence,dialogue_units,question_count,keywords_json)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                [(d["scene_id"], d["transcript"], d.get("first_dialogue"), d.get("last_dialogue"),
                  d["dialogue_seconds"], d["dialogue_density"], d["longest_silence"],
                  d["dialogue_units"], d["question_count"], json.dumps(d["keywords"]))
                 for d in documents],
            )
            db.executemany(
                "INSERT INTO scene_fts(scene_id,title,transcript) VALUES(?,?,?)",
                [(d["scene_id"], d["title"], d["transcript"]) for d in documents],
            )
            self.set_metadata({"scene_enrichment_status": "complete",
                               "scene_document_count": len(documents), "updated_at": utc_now()}, db=db)

    def scene_documents(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT s.id,s.start,s.end,s.title,s.review_status,d.*
                FROM scenes s JOIN scene_documents d ON d.scene_id=s.id ORDER BY s.start"""
            )
            result = []
            for row in rows:
                item = dict(row)
                item["keywords"] = json.loads(item.pop("keywords_json"))
                result.append(item)
            return result

    def replace_semantic_passages(self, passages: list[dict], *, model: str,
                                  dimensions: int) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM semantic_passages")
            db.executemany(
                """INSERT INTO semantic_passages(scene_id,start,end,text,embedding)
                VALUES(?,?,?,?,?)""",
                [(p["scene_id"], p["start"], p["end"], p["text"], p["embedding"])
                 for p in passages],
            )
            self.set_metadata({
                "semantic_index_status": "complete", "semantic_model": model,
                "semantic_dimensions": dimensions, "semantic_passage_count": len(passages),
                "updated_at": utc_now(),
            }, db=db)

    def semantic_passages(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,scene_id,start,end,text,embedding FROM semantic_passages ORDER BY id"
            )]

    def search_scenes(self, query: str, limit: int = 12) -> list[dict]:
        tokens = re.findall(r"[A-Za-z0-9']+", query)
        if not tokens:
            return []
        expression = " OR ".join(f'"{token}"' for token in tokens[:12])
        with self.connect() as db:
            rows = db.execute(
                """SELECT s.id,s.start,s.end,s.title,s.review_status,d.first_dialogue,
                d.last_dialogue,d.dialogue_density,d.longest_silence,d.keywords_json,
                bm25(scene_fts) AS rank,
                snippet(scene_fts,2,'<mark>','</mark>',' … ',22) AS excerpt
                FROM scene_fts JOIN scenes s ON s.id=CAST(scene_fts.scene_id AS INTEGER)
                JOIN scene_documents d ON d.scene_id=s.id
                WHERE scene_fts MATCH ? ORDER BY rank LIMIT ?""",
                (expression, limit),
            )
            result = []
            for row in rows:
                item = dict(row)
                item["keywords"] = json.loads(item.pop("keywords_json"))
                item["score"] = round(-float(item.pop("rank")), 4)
                result.append(item)
            return result

    def update_scene_review(self, scene_id: int, *, status: str | None = None,
                            title: str | None = None) -> dict:
        allowed = {"unreviewed", "approved", "boundary_problem"}
        with self.connect() as db:
            if status is not None:
                if status not in allowed:
                    raise ValueError("Invalid scene review status.")
                db.execute("UPDATE scenes SET review_status=? WHERE id=?", (status, scene_id))
            if title is not None:
                title = title.strip()[:160]
                if not title:
                    raise ValueError("Scene title cannot be empty.")
                db.execute("UPDATE scenes SET title=? WHERE id=?", (title, scene_id))
                db.execute("UPDATE scene_fts SET title=? WHERE scene_id=?", (title, str(scene_id)))
            row = db.execute("SELECT id,title,review_status FROM scenes WHERE id=?", (scene_id,)).fetchone()
            if not row:
                raise ValueError("Scene not found.")
            return dict(row)

    def stats(self) -> dict:
        with self.connect() as db:
            metadata = {row["key"]: json.loads(row["value"]) for row in db.execute("SELECT * FROM metadata")}
            counts = {
                "shots": db.execute("SELECT COUNT(*) FROM shots").fetchone()[0],
                "browser_shots": db.execute(
                    "SELECT COUNT(*) FROM shots WHERE selected_for_browser=1"
                ).fetchone()[0],
                "transcript_segments": db.execute("SELECT COUNT(*) FROM transcript_segments").fetchone()[0],
                "transcript_words": db.execute("SELECT COUNT(*) FROM transcript_words").fetchone()[0],
                "normalized_transcript": db.execute("SELECT COUNT(*) FROM normalized_transcript").fetchone()[0],
                "scenes": db.execute("SELECT COUNT(*) FROM scenes").fetchone()[0],
                "observations": db.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
                "scene_documents": db.execute("SELECT COUNT(*) FROM scene_documents").fetchone()[0],
                "semantic_passages": db.execute("SELECT COUNT(*) FROM semantic_passages").fetchone()[0],
            }
        return {"path": str(self.path), "metadata": metadata, "counts": counts}
