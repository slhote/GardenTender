# Direct endpoints call the same services as the LLM tools.
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import GardenAccess
from app.db import get_session
from app.dependencies import require_garden
from app.roles import GardenPermission
from app.services import plants

router = APIRouter(prefix="/gardens/{garden_id}/plants", tags=["plants"])


class UpdatePlantRequest(BaseModel):
    field: str
    value: str


@router.get("", response_model=list[plants.PlantResponse])
async def list_plants(
    access: GardenAccess = Depends(require_garden(GardenPermission.VIEW)), session: AsyncSession = Depends(get_session)
):
    return await plants.list_plants(session, access.garden.id)


@router.post("", response_model=plants.PlantResponse, status_code=status.HTTP_201_CREATED)
async def create_plant(
    body: plants.CreatePlantRequest,
    access: GardenAccess = Depends(require_garden(GardenPermission.PLANTS_CREATE)),
    session: AsyncSession = Depends(get_session),
):
    return await plants.create_plant(session, access.garden.id, access.actor, body)


@router.patch("/{plant_id}", response_model=plants.PlantResponse)
async def patch_plant(
    plant_id: int,
    patch: UpdatePlantRequest,
    access: GardenAccess = Depends(require_garden(GardenPermission.PLANTS_EDIT)),
    session: AsyncSession = Depends(get_session),
):
    return await plants.update_plant(session, access.garden.id, access.actor, plant_id, patch.field, patch.value)


@router.delete("/{plant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plant(
    plant_id: int,
    access: GardenAccess = Depends(require_garden(GardenPermission.PLANTS_DELETE)),
    session: AsyncSession = Depends(get_session),
):
    await plants.delete_plant(session, access.garden.id, access.actor, plant_id)
