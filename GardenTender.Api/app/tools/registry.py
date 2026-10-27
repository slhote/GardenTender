"""Single source of truth for tools: schema, handler, required permission, confirmation policy."""
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal

from datetime import datetime

from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Actor
from app.roles import GardenPermission, GardenRole, role_allows
from app.services import plants


@dataclass(frozen=True)
class ToolContext:
    """Who is chatting and in which garden. Built server-side from the token and membership, never from the model."""

    garden_id: int
    actor: Actor
    role: GardenRole

    def allows(self, permission: GardenPermission) -> bool:
        return role_allows(self.role, permission)


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[AsyncSession, ToolContext, BaseModel], Awaitable[object]]  # -> JSON-able
    permission: GardenPermission
    confirm: bool = False
    runs_on: Literal["server", "device"] = "server"

    def json_schema(self) -> dict:
        return self.input_model.model_json_schema()


class ListPlantsInput(BaseModel):
    pass


class UpdatePlantInput(BaseModel):
    plant_id: int
    field: Literal["name", "species", "notes", "water_every_days"]
    value: str


def _check_iso(v: str) -> str:
    try:
        datetime.fromisoformat(v)
    except ValueError:
        raise ValueError("must be an ISO 8601 local datetime, e.g. 2026-10-15T09:00")
    return v


class SetReminderInput(BaseModel):
    text: str
    time: str  # local ISO 8601

    _time = field_validator("time")(_check_iso)


class AddCalendarEventInput(BaseModel):
    title: str
    start: str  # local ISO 8601
    end: str | None = None

    _start = field_validator("start")(_check_iso)

    @field_validator("end")
    @classmethod
    def _end(cls, v):
        return None if v is None else _check_iso(v)


async def _device_only(*_):
    raise RuntimeError("Device tools run on the phone, not the server.")


async def _list_plants(session: AsyncSession, ctx: ToolContext, _: ListPlantsInput):
    return [p.model_dump() for p in await plants.list_plants(session, ctx.garden_id)]


async def _update_plant(session: AsyncSession, ctx: ToolContext, args: UpdatePlantInput):
    return (await plants.update_plant(session, ctx.garden_id, ctx.actor, args.plant_id, args.field, args.value)).model_dump()


async def _add_plant(session: AsyncSession, ctx: ToolContext, args: plants.NewPlant):
    return (await plants.create_plant(session, ctx.garden_id, ctx.actor, args)).model_dump()


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            name="list_plants",
            description="List the plants in this garden with their ids and care settings.",
            input_model=ListPlantsInput,
            handler=_list_plants,
            permission=GardenPermission.VIEW,
        ),
        Tool(
            name="add_plant",
            description="Add a plant to this garden.",
            input_model=plants.NewPlant,
            handler=_add_plant,
            permission=GardenPermission.PLANTS_CREATE,
            confirm=True,
        ),
        Tool(
            name="update_plant",
            description="Change one field of one plant in this garden. Use list_plants first to get the id.",
            input_model=UpdatePlantInput,
            handler=_update_plant,
            permission=GardenPermission.PLANTS_EDIT,
            confirm=True,
        ),
        Tool(
            name="set_reminder",
            description="Schedule a notification on the user's phone at a local time.",
            input_model=SetReminderInput,
            handler=_device_only,
            permission=GardenPermission.VIEW,  # personal, on the phone: any member
            runs_on="device",
        ),
        Tool(
            name="add_calendar_event",
            description="Open the user's calendar app with a prefilled event; the user saves it there.",
            input_model=AddCalendarEventInput,
            handler=_device_only,
            permission=GardenPermission.VIEW,
            confirm=True,
            runs_on="device",
        ),
    ]
}


def tools_for(ctx: ToolContext) -> list[Tool]:
    """Only tools the caller's garden role allows are ever shown to the model."""
    return [t for t in TOOLS.values() if ctx.allows(t.permission)]
