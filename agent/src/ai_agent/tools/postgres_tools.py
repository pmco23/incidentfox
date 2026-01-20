"""PostgreSQL tools for database queries and schema inspection."""

import json
import logging

logger = logging.getLogger(__name__)


def postgres_list_tables(
    database: str,
    schema: str = "public",
    host: str = "localhost",
    port: int = 5432,
    user: str | None = None,
    password: str | None = None,
) -> str:
    """
    List all tables in a PostgreSQL database schema.

    Args:
        database: Database name
        schema: Schema name (default: public)
        host: Database host
        port: Database port
        user: Database user
        password: Database password

    Returns:
        List of tables as JSON string
    """
    try:
        import psycopg2
    except ImportError:
        return json.dumps(
            {"error": "psycopg2 is required. Install with: pip install psycopg2-binary"}
        )

    try:
        conn = psycopg2.connect(
            database=database, user=user, password=password, host=host, port=port
        )
        cursor = conn.cursor()

        query = """
            SELECT
                table_name,
                pg_total_relation_size(quote_ident(table_schema) || '.' || quote_ident(table_name)) as size_bytes
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """

        cursor.execute(query, (schema,))
        tables = cursor.fetchall()

        result = []
        for table in tables:
            result.append(
                {
                    "table_name": table[0],
                    "size_bytes": table[1],
                    "size_mb": round(table[1] / (1024 * 1024), 2) if table[1] else 0,
                }
            )

        cursor.close()
        conn.close()

        return json.dumps(
            {
                "database": database,
                "schema": schema,
                "table_count": len(result),
                "tables": result,
            }
        )

    except Exception as e:
        logger.error(f"failed_to_list_postgres_tables: {e}")
        return json.dumps({"error": str(e)})


def postgres_describe_table(
    table_name: str,
    database: str,
    schema: str = "public",
    host: str = "localhost",
    port: int = 5432,
    user: str | None = None,
    password: str | None = None,
) -> str:
    """
    Get column details for a PostgreSQL table.

    Args:
        table_name: Table name
        database: Database name
        schema: Schema name (default: public)
        host: Database host
        port: Database port
        user: Database user
        password: Database password

    Returns:
        Table schema as JSON string
    """
    try:
        import psycopg2
    except ImportError:
        return json.dumps(
            {"error": "psycopg2 is required. Install with: pip install psycopg2-binary"}
        )

    try:
        conn = psycopg2.connect(
            database=database, user=user, password=password, host=host, port=port
        )
        cursor = conn.cursor()

        # Get columns
        query = """
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """

        cursor.execute(query, (schema, table_name))
        columns = cursor.fetchall()

        # Get primary keys
        pk_query = """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
        """

        cursor.execute(pk_query, (f"{schema}.{table_name}",))
        primary_keys = {row[0] for row in cursor.fetchall()}

        # Get foreign keys
        fk_query = """
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
        """

        cursor.execute(fk_query, (schema, table_name))
        foreign_keys = {
            row[0]: {"foreign_table": row[1], "foreign_column": row[2]}
            for row in cursor.fetchall()
        }

        # Get row count
        count_query = f"SELECT COUNT(*) FROM {schema}.{table_name}"
        cursor.execute(count_query)
        row_count = cursor.fetchone()[0]

        result = []
        for col in columns:
            col_name = col[0]
            result.append(
                {
                    "name": col_name,
                    "type": col[1],
                    "max_length": col[2],
                    "nullable": col[3] == "YES",
                    "default": col[4],
                    "primary_key": col_name in primary_keys,
                    "foreign_key": foreign_keys.get(col_name),
                }
            )

        cursor.close()
        conn.close()

        return json.dumps(
            {
                "database": database,
                "schema": schema,
                "table": table_name,
                "row_count": row_count,
                "column_count": len(result),
                "columns": result,
            }
        )

    except Exception as e:
        logger.error(f"failed_to_describe_postgres_table: {e}")
        return json.dumps({"error": str(e), "table": table_name})


def postgres_execute_query(
    query: str,
    database: str,
    host: str = "localhost",
    port: int = 5432,
    user: str | None = None,
    password: str | None = None,
    limit: int = 100,
) -> str:
    """
    Execute a SQL query against PostgreSQL and return results.

    Args:
        query: SQL query to execute
        database: Database name
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        limit: Maximum number of rows to return

    Returns:
        Query results as JSON string
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return json.dumps(
            {"error": "psycopg2 is required. Install with: pip install psycopg2-binary"}
        )

    try:
        conn = psycopg2.connect(
            database=database, user=user, password=password, host=host, port=port
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Add limit if not present
        query_lower = query.lower().strip()
        if "limit" not in query_lower:
            query = f"{query.rstrip(';')} LIMIT {limit}"

        cursor.execute(query)

        # For SELECT queries
        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            # Convert to list of dicts
            results = []
            for row in rows:
                row_dict = {}
                for col in columns:
                    val = row[col]
                    # Handle special types
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif isinstance(val, bytes):
                        val = val.decode("utf-8", errors="replace")
                    row_dict[col] = val
                results.append(row_dict)

            cursor.close()
            conn.close()

            return json.dumps(
                {
                    "success": True,
                    "row_count": len(results),
                    "columns": columns,
                    "rows": results,
                },
                default=str,
            )
        else:
            # For INSERT/UPDATE/DELETE
            conn.commit()
            rows_affected = cursor.rowcount
            cursor.close()
            conn.close()

            return json.dumps({"success": True, "rows_affected": rows_affected})

    except Exception as e:
        logger.error(f"postgres_query_failed: {e}")
        return json.dumps({"success": False, "error": str(e)})


# List of all Postgres tools for registration
POSTGRES_TOOLS = [
    postgres_list_tables,
    postgres_describe_table,
    postgres_execute_query,
]
