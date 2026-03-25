from asyncio import Future
import logging
from dataclasses import dataclass
from operator import inv

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder import db_schema as dbmodels
from homeassistant.components.recorder import get_instance as get_recorder_instance
from homeassistant.components.recorder.tasks import RecorderTask
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity import Entity
from sqlalchemy import (
    Select,
    delete,
    distinct,
    func,
    lambda_stmt,
    select,
    union_all,
    update,
)
from sqlalchemy.orm import Session

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EnsureStatesMetadataTask(RecorderTask):
    entity_id: str
    awaitable: Future

    def run(self, instance: Recorder) -> None:
        import ipdb

        ipdb.set_trace()
        pass
        """Handle the task."""
        LOGGER.debug(f"{self.entity_id}: enter ensure metadata")
        _recorder_get_or_create_states_metadata_id(instance, self.entity_id)
        LOGGER.debug(f"{self.entity_id}: leaving ensure metadata")

        self.awatible.set_result(None)


async def get_or_create_states_metadata_id(hass: HomeAssistant, entity: Entity) -> int:
    rec = get_recorder_instance(hass)
    task = EnsureStatesMetadataTask(entity_id=entity.entity_id, awaitable=Future())
    rec.queue_task(task)

    LOGGER.debug(f"Task enqueued waiting...")
    await task.awaitable
    LOGGER.debug(f"Task done!")

    # return 0

    return await rec.async_add_executor_job(
        _recorder_get_or_create_states_metadata_id, rec, entity.entity_id
    )


def _recorder_get_or_create_states_metadata_id(rec: Recorder, entity_id: str) -> int:
    session: Session = rec.event_session
    states_metadata_id = rec.states_meta_manager.get(entity_id, session, True)

    if states_metadata_id is None:
        meta = dbmodels.StatesMeta(entity_id=entity_id)

        session.add(meta)
        rec.states_meta_manager.add_pending(meta)

        session.commit()
        rec.states_meta_manager.post_commit_pending()

    states_metadata_id = rec.states_meta_manager.get(entity_id, session, True)
    assert states_metadata_id is not None

    return states_metadata_id


@dataclass(slots=True)
class DeleteInvalidStatesTask(RecorderTask):
    """Object to store statistics_id and unit to convert unit of statistics."""

    entity_id: str

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        _recorder_delete_invalid_states(instance, self.entity_id)


async def delete_invalid_states(hass: HomeAssistant, entity: Entity) -> list[State]:
    rec = get_recorder_instance(hass)
    # rec.queue_task(DeleteInvalidStatesTask(entity.entity_id))
    return []

    # return await rec.async_add_executor_job(
    #     _recorder_delete_invalid_states, rec, entity.entity_id
    # )


def _recorder_delete_invalid_states(rec: Recorder, entity_id: str) -> list[State]:
    session: Session = rec.event_session

    invalid = set(session.execute(entity_invalid_states_stmt(entity_id)).scalars())
    if not invalid:
        return []

    stmt = entity_states_stmt(entity_id).order_by(
        dbmodels.States.last_updated_ts.desc()
    )

    old_state = None
    for state in session.execute(stmt).scalars():
        if state in invalid:
            continue

        state.old_state = old_state
        old_state = state
        session.add(state)

    if old_state:
        old_state.old_state = None

    ret = []
    for x in invalid:
        x.entity_id = x.states_meta_rel.entity_id
        ret.append(x.to_native())
        session.delete(x)

    session.commit()
    rec.states_manager.reset()
    LOGGER.debug(f"{entity_id}: deleted {len(ret)} invalids")
    return ret


def entity_invalid_states_stmt(entity_id: str) -> Select:
    return entity_states_stmt(entity_id).where(
        dbmodels.States.state.in_([STATE_UNAVAILABLE, STATE_UNKNOWN])
    )


def entity_states_stmt(entity_id: str) -> Select:
    return (
        select(dbmodels.States)
        .join(dbmodels.StatesMeta)
        .where(dbmodels.StatesMeta.entity_id == entity_id)
    )
