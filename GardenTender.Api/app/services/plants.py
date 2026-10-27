"""Plant operations shared by the direct endpoints and the LLM tools.

Every query is scoped by `garden_id`; callers have already resolved the caller's access to that garden.
"""
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Actor
from app.errors import InvalidInput, NotFound
from app.models import PlantRow, QrCodeRow
from app.services import events
from app.services.text import normalize_name

NAME_MAX = 60
WATER_DAYS_RANGE = (1, 365)


class Plant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    species: str = ""
    notes: str = ""
    water_every_days: int = 7


class NewPlant(BaseModel):
    name: str
    species: str = ""
    notes: str = ""
    water_every_days: int = 7


EDITABLE_FIELDS = ("name", "species", "notes", "water_every_days")


def _water_days(value: int | str) -> int:
    try:
        days = int(value)
    except ValueError:
        raise InvalidInput("water_every_days must be an integer")
    lo, hi = WATER_DAYS_RANGE
    if not lo <= days <= hi:
        raise InvalidInput(f"water_every_days must be between {lo} and {hi}")
    return days


def validate_new(plant: NewPlant) -> NewPlant:
    """Normalizes and checks a new plant without saving it (also used when an approval request is filed)."""
    return plant.model_copy(
        update={"name": normalize_name(plant.name, "Plant name", NAME_MAX), "water_every_days": _water_days(plant.water_every_days)}
    )


async def list_plants(session: AsyncSession, garden_id: int) -> list[Plant]:
    rows = await session.scalars(select(PlantRow).where(PlantRow.garden_id == garden_id).order_by(PlantRow.id))
    return [Plant.model_validate(r) for r in rows]


async def create_plant(session: AsyncSession, garden_id: int, actor: Actor, plant: NewPlant, *, commit: bool = True) -> Plant:
    plant = validate_new(plant)
    row = PlantRow(garden_id=garden_id, created_by=actor.sub, **plant.model_dump())
    session.add(row)
    await session.flush()
    events.record(session, garden_id, actor, "plant.created", plant_id=row.id, name=row.name)
    if commit:
        await session.commit()
    return Plant.model_validate(row)


async def update_plant(session: AsyncSession, garden_id: int, actor: Actor, plant_id: int, field: str, value: str) -> Plant:
    if field not in EDITABLE_FIELDS:
        raise InvalidInput(f"Field must be one of {EDITABLE_FIELDS}")
    row = await _get(session, garden_id, plant_id)
    old = getattr(row, field)
    if field == "water_every_days":
        new = _water_days(value)
    elif field == "name":
        new = normalize_name(value, "Plant name", NAME_MAX)
    else:
        new = value
    setattr(row, field, new)
    events.record(session, garden_id, actor, "plant.updated", plant_id=plant_id, field=field, old=old, new=new)
    await session.commit()
    return Plant.model_validate(row)


async def delete_plant(session: AsyncSession, garden_id: int, actor: Actor, plant_id: int) -> None:
    row = await _get(session, garden_id, plant_id)
    # Explicit so it doesn't depend on the database enforcing ON DELETE CASCADE.
    await session.execute(delete(QrCodeRow).where(QrCodeRow.plant_id == plant_id))
    await session.delete(row)
    events.record(session, garden_id, actor, "plant.deleted", plant_id=plant_id, name=row.name)
    await session.commit()


async def _get(session: AsyncSession, garden_id: int, plant_id: int) -> PlantRow:
    row = await session.scalar(select(PlantRow).where(PlantRow.id == plant_id, PlantRow.garden_id == garden_id))
    if row is None:
        raise NotFound(f"No plant with id {plant_id!r}")
    return row
