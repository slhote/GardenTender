# Direct endpoints call the same services as the LLM tools.
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User, require_permission
from app.db import get_session
from app.services import plants

router = APIRouter(prefix="/plants", tags=["plants"])


class PlantPatch(BaseModel):
    field: str
    value: str


@router.get("", response_model=list[plants.Plant])
async def get_plants(user: User = Depends(require_permission("plants:read")), session: AsyncSession = Depends(get_session)):
    return await plants.list_plants(session, user.sub)


@router.patch("/{plant_id}", response_model=plants.Plant)
async def patch_plant(
    plant_id: int,
    patch: PlantPatch,
    user: User = Depends(require_permission("plants:write")),
    session: AsyncSession = Depends(get_session),
):
    return await plants.update_plant(session, user.sub, plant_id, patch.field, patch.value)
