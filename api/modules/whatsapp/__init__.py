from fastapi import APIRouter

from .webhook import router as webhook_router
from .send_reminder import router as send_reminder_router

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

router.include_router(webhook_router)
router.include_router(send_reminder_router)
