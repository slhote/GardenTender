"""Garden history. Callers record in the same session as the action and commit together."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Actor
from app.models import GardenEventRow


def record(session: AsyncSession, garden_id: int, actor: Actor, type: str, **payload) -> None:
    session.add(
        GardenEventRow(
            garden_id=garden_id, actor_sub=actor.sub, via_global_admin=actor.via_global_admin, type=type, payload=payload
        )
    )
