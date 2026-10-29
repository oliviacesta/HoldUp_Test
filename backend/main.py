import os
import json
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import asyncpg
from dotenv import load_dotenv
import jwt
from jwt import PyJWKClient

# ==============================================================================
# 1. ENVIRONMENT & CONFIGURATION
# ==============================================================================
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")

# Automatically fetch Supabase's public JWKS endpoint for ES256 token validation
JWKS_URL = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
jwk_client = PyJWKClient(JWKS_URL)


# ==============================================================================
# 2. FASTAPI APPLICATION INITIALIZATION
# ==============================================================================
app = FastAPI(
    title="HoldUp API",
    description="Backend API for climbing gym management and route building.",
    version="0.3.0"
)

# Security scheme to extract Bearer tokens from the Authorization header
security = HTTPBearer()

# ==============================================================================
# 3. DATABASE CONNECTION POOL LIFECYCLE & CODECS
# ==============================================================================
db_pool = None


async def init_connection(conn):
    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )


@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        init=init_connection,
        statement_cache_size=0,
        min_size=1,
        max_inactive_connection_lifetime=30,
        command_timeout=30
    )


@app.on_event("shutdown")
async def shutdown():
    global db_pool
    if db_pool:
        await db_pool.close()


# ==============================================================================
# 4. AUTHENTICATION DEPENDENCY (JWT VALIDATION)
# ==============================================================================
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token, 
            signing_key.key, 
            algorithms=["ES256"], 
            options={"verify_aud": False}
        )
        
        supabase_user_id = payload.get("sub")
        if not supabase_user_id:
            raise HTTPException(status_code=401, detail="Token missing subject identifier")

        async with db_pool.acquire() as connection:
            query = """
                SELECT u.id::text as user_id, u.gym_id::text, u.name, u.role_id, r.role_name, r.permissions
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.id = $1::uuid;
            """
            user_record = await connection.fetchrow(query, supabase_user_id)
            
            if not user_record:
                raise HTTPException(
                    status_code=403, 
                    detail="User profile not found in database. Please contact your administrator."
                )

            return {
                "sub": supabase_user_id,
                "email": payload.get("email"),
                "user_id": user_record["user_id"],
                "gym_id": user_record["gym_id"],
                "name": user_record["name"],
                "role_id": user_record["role_id"],  # <--- Included for RBAC checking
                "role": user_record["role_name"],
                "permissions": user_record["permissions"]
            }

    except Exception as e:
        print("Auth Error:", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


def require_role_id(required_role_id: int):
    """
    Dependency factory that checks if the authenticated user has the required role_id.
    """
    def role_dependency(current_user: dict = Depends(get_current_user)):
        if current_user.get("role_id") != required_role_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Your role does not have permission to perform this action."
            )
        return current_user
    return role_dependency

# ==============================================================================
# 5. PYDANTIC SCHEMAS (DATA VALIDATION & SERIALIZATION)
# ==============================================================================

class HoldCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    hold_type: Optional[str] = None
    image_url: Optional[str] = None
    model_3d_url: Optional[str] = None


class HoldInventoryCreate(BaseModel):
    gym_id: str
    hold_catalog_id: str
    color: str
    status: Optional[str] = "available"


class RouteCreate(BaseModel):
    gym_id: str
    name: str
    color: Optional[str] = None
    grade: Optional[str] = None
    location: Optional[str] = None
    holds_in_space: Optional[dict] = {}


# ==============================================================================
# 6. API ROUTE ENDPOINTS
# ==============================================================================

@app.get("/")
async def root():
    return {"message": "Pipeline Skeleton API is active"}


# --- PROTECTED TEST ENDPOINT ---
@app.get("/auth/protected-test")
async def protected_test(current_user: dict = Depends(get_current_user)):
    return {
        "message": "You successfully accessed a protected route with an ES256 token!",
        "user_id": current_user.get("sub"),
        "email": current_user.get("email")
    }

# --- HOLDS CATALOG ENDPOINTS ---

@app.post("/holds-catalogue", status_code=status.HTTP_201_CREATED)
async def create_hold(hold: HoldCreate, current_user: dict = Depends(get_current_user)):
    """
    Creates a new master hold item in the global hold catalogue.
    """
    async with db_pool.acquire() as connection:
        query = """
            INSERT INTO hold_catalogue (name, brand, manufacturer, type, image_url, model_3d_url)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id::text, name, brand, manufacturer, type AS hold_type, image_url, model_3d_url;
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


@app.get("/holds-catalogue", response_model=List[dict])
async def get_holds(current_user: dict = Depends(get_current_user)):
    """
    Fetches all items from the master hold catalogue.
    """
    async with db_pool.acquire() as connection:
        query = "SELECT id::text, name, brand, manufacturer, type AS hold_type, image_url, model_3d_url FROM hold_catalogue"
        rows = await connection.fetch(query)
        return [dict(row) for row in rows]


# --- HOLD INVENTORY ENDPOINTS ---

@app.post("/hold-inventory", status_code=status.HTTP_201_CREATED)
async def create_hold_inventory(item: HoldInventoryCreate, current_user: dict = Depends(get_current_user)):
    """
    Assigns a physical hold from the catalogue to a specific gym's inventory.
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
async def get_gym_inventory(gym_id: str, current_user: dict = Depends(get_current_user)):
    """
    Fetches all physical hold inventory for a specific gym, joining with master catalogue details.
    """
    async with db_pool.acquire() as connection:
        query = """
            SELECT hi.id::text, hi.color, hi.status, h.name as hold_name, h.brand, h.type as hold_type, h.model_3d_url
            FROM hold_inventory hi
            JOIN hold_catalogue h ON hi.hold_catalog_id = h.id
            WHERE hi.gym_id = $1::uuid;
        """
        rows = await connection.fetch(query, gym_id)
        return [dict(row) for row in rows]

@app.delete("/hold-inventory/{inventory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hold_inventory(
    inventory_id: str, 
    current_user: dict = Depends(require_role_id(1))  # <--- Restricted to role_id 1 only
):
    """
    Deletes a physical hold from the gym's inventory. 
    Restricted strictly to users with role_id == 1.
    """
    async with db_pool.acquire() as connection:
        query = "DELETE FROM hold_inventory WHERE id = $1::uuid;"
        result = await connection.execute(query, inventory_id)
        
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Hold inventory item not found")

# --- ROUTES ENDPOINTS ---

@app.post("/routes", status_code=status.HTTP_201_CREATED)
async def create_route(route: RouteCreate, current_user: dict = Depends(get_current_user)):
    """
    Creates a new route mapped to a gym, automatically binding the setter_id 
    using the authenticated user's ID from Supabase Auth.
    """
    setter_id = current_user.get("sub")
    async with db_pool.acquire() as connection:
        query = """
            INSERT INTO routes (gym_id, setter_id, name, color, grade, location, holds_in_space)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::jsonb)
            RETURNING id::text, gym_id::text, setter_id::text, name, color, grade, location, is_active, holds_in_space, created_at;
        """
        row = await connection.fetchrow(
            query,
            route.gym_id,
            setter_id,
            route.name,
            route.color,
            route.grade,
            route.location,
            route.holds_in_space
        )
        return dict(row)


@app.get("/routes", response_model=List[dict])
async def get_routes():
    """
    Fetches all routes ordered by creation date (newest first).
    """
    async with db_pool.acquire() as connection:
        query = """
            SELECT id::text, setter_id::text, name, color, grade, 
                   location, is_active, holds_in_space, created_at
            FROM routes
            ORDER BY created_at DESC;
        """
        rows = await connection.fetch(query)
        return [dict(row) for row in rows]


@app.get("/routes/{route_id}")
async def get_route(route_id: str, current_user: dict = Depends(get_current_user)):
    """
    Fetches a single route by its ID.
    """
    async with db_pool.acquire() as connection:
        query = """
            SELECT id::text, gym_id::text, setter_id::text, name, color, grade, location, is_active, holds_in_space, created_at
            FROM routes
            WHERE id = $1::uuid;
        """
        try:
            row = await connection.fetchrow(query, route_id)
        except asyncpg.exceptions.DataError:
            raise HTTPException(status_code=400, detail="Invalid route ID")
        if row is None:
            raise HTTPException(status_code=404, detail="Route not found")
        return dict(row)
