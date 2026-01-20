from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from .EmbeddingModels import BaseEmbeddingModel

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


@dataclass(frozen=True)
class EmbeddingCacheKey:
    model_id: str
    text_sha256: str


class EmbeddingCache:
    """
    Simple persistent embedding cache (SQLite).

    Stores float32 embeddings as BLOBs keyed by (model_id, sha256(text)).
    Thread-safe for concurrent reads/writes within a single process.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # IMPORTANT: sqlite3 connections are notoriously fragile when shared across threads,
        # even with check_same_thread=False and a Python lock (we observed segfaults on macOS).
        # Use one connection per thread instead.
        self._tls = threading.local()

        # Initialize schema using a one-off connection.
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
              model_id TEXT NOT NULL,
              text_sha256 TEXT NOT NULL,
              dim INTEGER NOT NULL,
              vec BLOB NOT NULL,
              PRIMARY KEY (model_id, text_sha256)
            );
            """)
        conn.commit()
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        c = getattr(self._tls, "conn", None)
        if c is None:
            c = sqlite3.connect(str(self.path), timeout=30)
            c.execute("PRAGMA journal_mode=WAL;")
            self._tls.conn = c
        return c

    def get(self, key: EmbeddingCacheKey) -> Optional[np.ndarray]:
        with self._lock:
            cur = self._conn().execute(
                "SELECT dim, vec FROM embeddings WHERE model_id=? AND text_sha256=?",
                (key.model_id, key.text_sha256),
            )
            row = cur.fetchone()
        if row is None:
            return None
        dim, vec = row
        arr = np.frombuffer(vec, dtype=np.float32)
        if int(dim) != int(arr.shape[0]):
            return None
        return arr

    def put(self, key: EmbeddingCacheKey, embedding: np.ndarray) -> None:
        emb = np.asarray(embedding, dtype=np.float32).reshape(-1)
        with self._lock:
            self._conn().execute(
                "INSERT OR REPLACE INTO embeddings(model_id, text_sha256, dim, vec) VALUES (?,?,?,?)",
                (key.model_id, key.text_sha256, int(emb.shape[0]), emb.tobytes()),
            )
            self._conn().commit()


class CachedEmbeddingModel(BaseEmbeddingModel):
    """
    Wrap any BaseEmbeddingModel with a persistent on-disk cache.
    """

    def __init__(self, model: BaseEmbeddingModel, cache: EmbeddingCache, model_id: str):
        self.model = model
        self.cache = cache
        self.model_id = model_id

    def create_embedding(self, text):
        # Normalize like OpenAIEmbeddingModel does.
        t = (text or "").replace("\n", " ")
        key = EmbeddingCacheKey(model_id=self.model_id, text_sha256=_sha256_text(t))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        emb = self.model.create_embedding(t)
        self.cache.put(key, np.asarray(emb, dtype=np.float32))
        return emb
