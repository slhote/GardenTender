"""Plant operations shared by the direct endpoints and the LLM tools.

Every query is scoped by `user_id` (the Auth0 `sub`), which is how ownership is enforced.
"""
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlantRow


class Plant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    species: str = ""
    notes: str = ""
    water_every_days: int = 7


class PlantError(Exception):
    pass


EDITABLE_FIELDS = ("name", "species", "notes", "water_every_days")


async def list_plants(session: AsyncSession, user_id: str) -> list[Plant]:
    rows = (await session.scalars(select(PlantRow).where(PlantRow.user_id == user_id).order_by(PlantRow.id))).all()
    if not rows:
        # Demo behavior until there's a way to add plants: seed a new user's garden on first read.
        rows = [
            PlantRow(user_id=user_id, name="Fern", species="Nephrolepis exaltata", water_every_days=3),
            PlantRow(user_id=user_id, name="Basil", species="Ocimum basilicum", water_every_days=2),
        ]
        session.add_all(rows)
        await session.commit()
    return [Plant.model_validate(r) for r in rows]


async def update_plant(session: AsyncSession, user_id: str, plant_id: int, field: str, value: str) -> Plant:
    if field not in EDITABLE_FIELDS:
        raise PlantError(f"Field must be one of {EDITABLE_FIELDS}")
    row = await session.scalar(select(PlantRow).where(PlantRow.id == plant_id, PlantRow.user_id == user_id))
    if row is None:
        raise PlantError(f"No plant with id {plant_id!r}")
    if field == "water_every_days":
        try:
            days = int(value)
        except ValueError:
            raise PlantError("water_every_days must be an integer")
        if not 1 <= days <= 365:
            raise PlantError("water_every_days must be between 1 and 365")
        row.water_every_days = days
    else:
        setattr(row, field, value)
    await session.commit()
    return Plant.model_validate(row)
