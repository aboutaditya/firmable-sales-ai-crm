from __future__ import annotations

from pathlib import Path
import base64
import json


def query_companies(
    parquet_path: str | Path,
    *,
    company_id: str | None = None,
    country: str | None = None,
    min_score: int | None = None,
    industry: str | None = None,
    min_employee_count: int | None = None,
    signals: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
    cursor: str | None = None,
) -> list[dict]:
    """Return ranked company profiles from Parquet using DuckDB.

    Filters are parameterized, and the path is escaped before being placed in
    DuckDB's table-function expression.
    """
    if limit < 1 or limit > 10_000:
        raise ValueError("limit must be between 1 and 10000")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if min_employee_count is not None and min_employee_count < 0:
        raise ValueError("min_employee_count must be non-negative")
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB queries require: pip install -e '.[analytics]'") from exc

    path = str(Path(parquet_path).resolve()).replace("'", "''")
    clauses = []
    params: list[object] = []
    if company_id:
        clauses.append("company_id = ?")
        params.append(company_id)
    if country:
        clauses.append("country = ?")
        params.append(country)
    if min_score is not None:
        clauses.append("security_score >= ?")
        params.append(min_score)
    if industry:
        clauses.append("industry = ?")
        params.append(industry)
    if min_employee_count is not None:
        clauses.append("employee_count >= ?")
        params.append(min_employee_count)
    for signal in signals or []:
        if signal not in {"rdp", "database", "exchange", "vulnerability", "critical", "eol"}:
            raise ValueError(f"unsupported signal: {signal}")
        column = {"rdp": "exposed_rdp", "database": "exposed_database", "exchange": "exposed_exchange"}.get(signal)
        if column:
            clauses.append(f"{column} = true")
        else:
            column = {"vulnerability": "vulnerability_count", "critical": "critical_vulnerability_count", "eol": "eol_product_count"}[signal]
            clauses.append(f"{column} > 0")
    if cursor:
        try:
            cursor_score, cursor_id = decode_cursor(cursor)
        except (ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ValueError("cursor is invalid") from exc
        clauses.append("(security_score < ? OR (security_score = ? AND company_id > ?))")
        params.extend((cursor_score, cursor_score, cursor_id))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT *
        FROM read_parquet('{path}')
        {where}
        ORDER BY security_score DESC, company_id ASC
        LIMIT ? OFFSET ?
    """
    params.extend((limit, offset))
    with duckdb.connect() as connection:
        rows = connection.execute(query, params).fetchall()
        columns = [column[0] for column in connection.description]
    return [dict(zip(columns, row)) for row in rows]


def encode_cursor(row: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps([row["security_score"], row["company_id"]]).encode()).decode()


def decode_cursor(cursor: str) -> tuple[int, str]:
    decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    return int(decoded[0]), str(decoded[1])
