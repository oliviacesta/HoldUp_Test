import os
import json
from typing import List, Optional
from fastapi import FastAPI, Query
from pydantic import BaseModel
import asyncpg
from dotenv import load_dotenv

# ==============================================================================
# 1. ENVIRONMENT & CONFIGURATION
# ==============================================================================
# Read local environment variables from the `.env` file into `os.environ`.
# Keeps sensitive database credentials (like passwords) out of source code.
load_dotenv()

# Retrieve the PostgreSQL connection string configured in `.env`.
DATABASE_URL = os.getenv("DATABASE_URL")


# ==============================================================================
# 2. FASTAPI APPLICATION INITIALIZATION
# ==============================================================================
# Instantiates the core FastAPI application to handle routing and Swagger docs.
app = FastAPI(
    title="HoldUp Test API",
    description="Skeleton API for route visualization and hold inventory pipeline testing.",
    version="0.1.0"
)


# ==============================================================================
# 3. DATABASE CONNECTION POOL LIFECYCLE & CODECS
# ==============================================================================
db_pool = None


async def init_connection(conn):
    """
    Configures asyncpg to automatically decode PostgreSQL JSONB fields directly
    into native Python dictionaries using json.loads.
    """
    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )


@app.on_event("startup")
async def startup():
    """
    Executes automatically when the FastAPI server starts up.
    Initializes the connection pool with `statement_cache_size=0` to prevent
    DuplicatePreparedStatementError when connecting via Supabase's PgBouncer pooler.
    """
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        init=init_connection,
        statement_cache_size=0
    )


@app.on_event("shutdown")
async def shutdown():
    """
    Executes automatically when the FastAPI server shuts down.
    Gracefully closes all active pool connections to prevent leaked sockets.
    """
    global db_pool
    if db_pool:
        await db_pool.close()


# ==============================================================================
# 4. PYDANTIC SCHEMAS (DATA VALIDATION & SERIALIZATION)
# ==============================================================================
class HoldItem(BaseModel):
    """
    Defines the shape and types of data returned by the /holds endpoint.
    """
    id: str
    hold_code: str
    color: str
    hold_type: str
    status: str
    metadata: Optional[dict] = {}  # Holds nested JSON metadata (e.g., brand, size, CV confidence)


# ==============================================================================
# 5. API ROUTE ENDPOINTS
# ==============================================================================

@app.get("/")
async def root():
    """
    Root endpoint serving as a health check.
    """
    return {"message": "Pipeline Skeleton API is active"}


@app.get("/holds", response_model=List[HoldItem])
async def get_hold_inventory(
    status: Optional[str] = Query(None, description="Filter by status, e.g. available, on_wall, maintenance")
):
    """
    Fetches hold inventory items from Supabase PostgreSQL.
    Supports optional filtering by hold status via URL query parameters (e.g., /holds?status=available).
    """
    async with db_pool.acquire() as connection:
        if status:
            # Explicitly cast UUID `id` to `text` so asyncpg outputs a standard string.
            query = "SELECT id::text, hold_code, color, hold_type, status, metadata FROM hold_inventory WHERE status = $1"
            rows = await connection.fetch(query, status)
        else:
            query = "SELECT id::text, hold_code, color, hold_type, status, metadata FROM hold_inventory"
            rows = await connection.fetch(query)

        # Convert asyncpg Record objects directly to dicts.
        # `metadata` is automatically decoded to a Python dict by the jsonb codec in init_connection.
        return [dict(row) for row in rows]

@app.get("/testing")
async def get_stupid(
):
    return ['successful test']