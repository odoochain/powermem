"""
API v1 + v2 routes
"""

from fastapi import APIRouter

from .memories import router as memories_router, router_v2 as memories_router_v2
from .search import router as search_router, router_v2 as search_router_v2
from .users import router as users_router, router_v2 as users_router_v2
from .agents import router as agents_router, router_v2 as agents_router_v2
from .system import router as system_router, router_v2 as system_router_v2

# v1 router (/api/v1)
router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include sub-routers: search before memories so GET /memories/search
# is matched by the search route, not by GET /memories/{memory_id}
router.include_router(search_router)
router.include_router(memories_router)
router.include_router(users_router)
router.include_router(agents_router)
router.include_router(system_router)

# v2 router (/api/v2) — per-request config, all POST
router_v2 = APIRouter(prefix="/api/v2", tags=["v2"])

router_v2.include_router(search_router_v2)
router_v2.include_router(memories_router_v2)
router_v2.include_router(users_router_v2)
router_v2.include_router(agents_router_v2)
router_v2.include_router(system_router_v2)
