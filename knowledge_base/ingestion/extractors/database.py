"""Database extractors for SQL and NoSQL databases."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Dict, Optional

from ingestion.extractors.base import BaseExtractor
from ingestion.metadata import ExtractedContent, SourceMetadata


class DatabaseExtractor(BaseExtractor):
    """Extract content from databases."""

    def __init__(
        self,
        db_type: str,
        connection_string: Optional[str] = None,
        query: Optional[str] = None,
        table_name: Optional[str] = None,
    ):
        """
        Initialize database extractor.

        Args:
            db_type: Type of database ("postgresql", "mysql", "mongodb", "sqlite")
            connection_string: Database connection string
            query: SQL query or MongoDB query
            table_name: Table/collection name
        """
        self.db_type = db_type
        self.connection_string = connection_string
        self.query = query
        self.table_name = table_name

    def can_handle(self, source: str) -> bool:
        """Check if source is a database connection string."""
        return source.startswith(
            ("postgresql://", "mysql://", "mongodb://", "sqlite://")
        )

    def extract(self, source: str, **kwargs) -> ExtractedContent:
        """Extract content from database."""
        start_time = time.time()
        connection_string = source or self.connection_string
        query = kwargs.get("query") or self.query
        table_name = kwargs.get("table_name") or self.table_name

        source_id = hashlib.sha1(
            f"{connection_string}:{query or table_name}".encode()
        ).hexdigest()
        metadata = SourceMetadata(
            source_type=f"database_{self.db_type}",
            source_url=connection_string or "database",
            source_id=source_id,
            ingested_at=datetime.utcnow(),
            original_format="database",
            mime_type="application/database",
            extraction_method="database_query",
        )

        if self.db_type in ("postgresql", "mysql", "sqlite"):
            text = self._extract_sql(connection_string, query, table_name)
        elif self.db_type == "mongodb":
            text = self._extract_mongodb(connection_string, query, table_name)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

        duration = time.time() - start_time
        metadata.processing_duration_seconds = duration
        metadata.processing_steps.append("database_extraction")

        return ExtractedContent(
            text=text,
            metadata=metadata,
        )

    def _extract_sql(
        self, connection_string: str, query: Optional[str], table_name: Optional[str]
    ) -> str:
        """Extract from SQL database."""
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(connection_string)

            if query:
                sql_query = query
            elif table_name:
                sql_query = f"SELECT * FROM {table_name} LIMIT 1000"
            else:
                raise ValueError("Either query or table_name must be provided")

            with engine.connect() as conn:
                result = conn.execute(text(sql_query))
                rows = result.fetchall()
                columns = result.keys()

                # Format as markdown table
                parts = ["## Database Query Results\n\n"]
                parts.append("| " + " | ".join(columns) + " |")
                parts.append("| " + " | ".join(["---"] * len(columns)) + " |")

                for row in rows:
                    cells = [str(cell or "") for cell in row]
                    parts.append("| " + " | ".join(cells) + " |")

                return "\n".join(parts)

        except ImportError:
            raise ImportError("sqlalchemy is required for SQL database extraction")
        except Exception as e:
            raise Exception(f"SQL extraction failed: {e}") from e

    def _extract_mongodb(
        self,
        connection_string: str,
        query: Optional[Dict],
        collection_name: Optional[str],
    ) -> str:
        """Extract from MongoDB."""
        try:
            from pymongo import MongoClient

            client = MongoClient(connection_string)
            db = client.get_database()

            if not collection_name:
                raise ValueError("collection_name must be provided for MongoDB")

            collection = db[collection_name]

            # Execute query
            if query:
                cursor = collection.find(query).limit(1000)
            else:
                cursor = collection.find().limit(1000)

            # Format results
            parts = [f"## MongoDB Collection: {collection_name}\n\n"]
            for doc in cursor:
                import json

                parts.append(
                    f"### Document\n```json\n{json.dumps(doc, indent=2, default=str)}\n```\n"
                )

            return "\n".join(parts)

        except ImportError:
            raise ImportError("pymongo is required for MongoDB extraction")
        except Exception as e:
            raise Exception(f"MongoDB extraction failed: {e}") from e
