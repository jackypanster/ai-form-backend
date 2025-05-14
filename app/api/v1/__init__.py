from fastapi import APIRouter
from .endpoints import form_filler

api_router = APIRouter()
api_router.include_router(form_filler.router, tags=["Form Filler"]) 