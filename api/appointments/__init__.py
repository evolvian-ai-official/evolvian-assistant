from fastapi import APIRouter

from .routes_register import router as register_router
from .routes_update_status import router as update_status_router
from .routes_log_usage import router as log_usage_router

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

router.include_router(register_router)
router.include_router(update_status_router)
router.include_router(log_usage_router)
