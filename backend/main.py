import os
import json
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException, status
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
    version="0.2.0"
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

# For creating a master hold catalog entry
class HoldCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    hold_type: Optional[str] = None
    image_url: Optional[str] = None
    model_3d_url: Optional[str] = None


# For creating a physical gym inventory entry
class HoldInventoryCreate(BaseModel):
    gym_id: str
    hold_catalog_id: str
    color: str
    status: Optional[str] = "available"


# ==============================================================================
# 5. API ROUTE ENDPOINTS
# ==============================================================================

@app.get("/")
async def root():
    return {"message": "Pipeline Skeleton API is active"}


# --- HOLDS CATALOG ENDPOINTS ---

@app.post("/holds", status_code=status.HTTP_201_CREATED)
async def create_hold(hold: HoldCreate):
    """
    Creates a new master hold item in the global holds catalog.
    """
    async with db_pool.acquire() as connection:
        # if not have the required field, send 400 back
        query = """
            INSERT INTO holds (name, brand, manufacturer, hold_type, image_url, model_3d_url)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id::text, name, brand, manufacturer, hold_type, image_url, model_3d_url;
        """
        row = await connection.fetchrow(
            query,
            hold.name,
            hold.brand,
            hold.manufacturer,
            hold.hold_type,
            hold.image_url,
            hold.model_3d_url
        )
        return dict(row)


@app.get("/holds", response_model=List[dict])
async def get_holds():
    """
    Fetches all items from the master holds catalog.
    """
    async with db_pool.acquire() as connection:
        query = "SELECT id::text, name, brand, manufacturer, hold_type, image_url, model_3d_url FROM holds"
        rows = await connection.fetch(query)
        return [dict(row) for row in rows]


# --- HOLD INVENTORY ENDPOINTS ---

@app.post("/hold-inventory", status_code=status.HTTP_201_CREATED)
async def create_hold_inventory(item: HoldInventoryCreate):
    """
    Assigns a physical hold from the catalog to a specific gym's inventory.
    """
    async with db_pool.acquire() as connection:
        query = """
            INSERT INTO hold_inventory (gym_id, hold_catalog_id, color, status)
            VALUES ($1::uuid, $2::uuid, $3, $4)
            RETURNING id::text, gym_id::text, hold_catalog_id::text, color, status;
        """
        try:
            row = await connection.fetchrow(
                query,
                item.gym_id,
                item.hold_catalog_id,
                item.color,
                item.status
            )
            return dict(row)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.get("/hold-inventory/{gym_id}", response_model=List[dict])
async def get_gym_inventory(gym_id: str):
    """
    Fetches all physical hold inventory for a specific gym, joining with the master hold catalog details.
    """
    async with db_pool.acquire() as connection:
        query = """
            SELECT hi.id::text, hi.color, hi.status, h.name as hold_name, h.brand, h.hold_type, h.model_3d_url
            FROM hold_inventory hi
            JOIN holds h ON hi.hold_catalog_id = h.id
            WHERE hi.gym_id = $1::uuid;
        """
        rows = await connection.fetch(query, gym_id)
        return [dict(row) for row in rows]


@app.get("/testing")
async def get_stupid():
    return ['successful test']