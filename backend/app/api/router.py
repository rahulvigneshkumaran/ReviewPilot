from fastapi import APIRouter

from app.api.v1 import auth, repositories, reviews, analytics, webhooks

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(repositories.router, prefix="/repositories", tags=["Repositories"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["Reviews"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
