"""PostgreSQL-only project persistence for MASTER CAD AI. No SQLite fallback."""
import os
import uuid
import json
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import Json, RealDictCursor


def dsn():
    url=os.environ.get("DATABASE_URL","").strip()
    if not url or not url.startswith(("postgresql://","postgres://")):
        raise RuntimeError("DATABASE_URL PostgreSQL obbligatorio. Collega Postgres al servizio Railway.")
    return url


@contextmanager
def connect():
    connection=psycopg2.connect(dsn(),connect_timeout=8)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cad_projects (
                    id UUID PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT 'Progetto CAD',
                    spec JSONB NOT NULL,
                    history JSONB NOT NULL,
                    step_file BYTEA NOT NULL,
                    stl_file BYTEA NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS cad_projects_created_idx ON cad_projects(created_at DESC)")


def save_model(project_id, name, spec, history, step_data, stl_data):
    token=uuid.UUID(project_id)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cad_projects(id,name,spec,history,step_file,stl_file)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (token,str(name or "Progetto CAD")[:180],Json(spec),Json(history),
                  psycopg2.Binary(step_data),psycopg2.Binary(stl_data)))


def project_list(limit=30):
    with connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id::text AS id, name, spec, history, created_at
                FROM cad_projects ORDER BY created_at DESC LIMIT %s
            """,(max(1,min(int(limit),100)),))
            result=cur.fetchall()
            return [
                dict(item,created_at=item["created_at"].isoformat())
                for item in result
            ]


def get_project(project_id):
    token=uuid.UUID(project_id)
    with connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id::text AS id, name, spec, history, created_at
                FROM cad_projects WHERE id=%s
            """,(token,))
            result=cur.fetchone()
            if result:
                result["created_at"]=result["created_at"].isoformat()
            return result


def get_export(project_id, fmt):
    if fmt not in ("step","stl"):
        raise ValueError("Formato non valido")
    token=uuid.UUID(project_id)
    col="step_file" if fmt=="step" else "stl_file"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT "+col+" FROM cad_projects WHERE id=%s",(token,))
            row=cur.fetchone()
            return bytes(row[0]) if row else None
