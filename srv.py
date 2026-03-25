import functools
import logging
from datetime import datetime
from typing import Any, cast
from bluetooth_adapters import get_adapters

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder import get_instance as get_recorder_instance
from homeassistant.components.recorder.db_schema import JSON_DUMP
from homeassistant.components.recorder.db_schema import (
    StateAttributes as DBStateAttributes,
)
from homeassistant.components.recorder.db_schema import States as DBStates
from homeassistant.components.recorder.db_schema import StatesMeta as DBStatesMeta
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.core import State as CoreState
from homeassistant.core import dt_util
from homeassistant.helpers.entity import Entity
from sqlalchemy import Select, not_, select
from sqlalchemy.orm import Session

from .patches import _build_attributes, _stringify_state
from .state import HistoricalState

TimestampState = tuple[float, Any]
LOGGER = logging.getLogger(__name__)


def display_ts(ts: float) -> datetime:
    return dt_util.as_local(dt_util.utc_from_timestamp(ts))


def recorder_job(hass: HomeAssistant):
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            rec = get_recorder_instance(hass)
            return await rec.async_add_executor_job(fn, rec, *args, **kwargs)

        return wrapper

    return decorator


async def is_available_on(entity: Entity, *, hass: HomeAssistant | None = None) -> bool:
    hass = hass or entity.hass

    @recorder_job(hass)
    def fn(rec: Recorder) -> int | None:
        with rec.get_session() as sess:
            return rec.states_meta_manager.get(entity.entity_id, sess, True)

    metadata_id = await fn()

    return metadata_id is not None


async def save_historical_states(
    entity: Entity,
    hist_states: list[HistoricalState],
    *,
    overwrite: bool = False,
    hass: HomeAssistant | None = None,
) -> list[CoreState]:

    def fn(rec, hist_states) -> list[CoreState]:
        with rec.get_session() as session:
            states_meta = rec.states_meta_manager.get(entity.entity_id, session, True)
            assert states_meta is not None

            # Unlink states
            stmt = _get_all_states_stmt(entity.entity_id).order_by(
                DBStates.last_updated_ts.desc()
            )
            for x in session.execute(stmt).scalars():
                x.old_state = None

            # Delete invalid states
            stmt = _get_invalid_states_stmt(entity.entity_id)
            for x in session.execute(stmt).scalars():
                session.delete(x)

            return []

            # latest_state = _get_latest_existing_state(session, entity.entity_id)
            # if latest_state:
            #     assert latest_state.last_updated_ts is not None
            #     cutoff = latest_state.last_updated_ts
            # else:
            #     cutoff = 0.0

            # LOGGER.debug(
            #     f"{entity.entity_id}: discarting states before {display_ts(cutoff)}"
            # )

            # hist_states = [x for x in hist_states if x.ts > cutoff]
            # if not hist_states:
            #     LOGGER.debug(f"{entity.entity_id}: no states left after cutoff")
            #     return []

            # LOGGER.debug(
            #     f"{entity.entity_id}: "
            #     + f"{len(hist_states)} left spanning between "
            #     + f"{display_ts(hist_states[0].ts)} and {display_ts(hist_states[-1].ts)}"
            # )

            # db_states: list[DBStates] = []
            # base_attrs_dict = _build_attributes(entity)
            # import ipdb

            # ipdb.set_trace()
            # pass
            # for idx, hist_state in enumerate(hist_states):

            #     attrs_as_dict = base_attrs_dict | hist_state.attributes
            #     attrs_as_str = JSON_DUMP(attrs_as_dict)
            #     attrs_as_bytes = (
            #         b"{}" if hist_state.state is None else attrs_as_str.encode("utf-8")
            #     )
            #     attrs_hash = DBStateAttributes.hash_shared_attrs_bytes(attrs_as_bytes)

            #     state_attributes = DBStateAttributes(
            #         hash=attrs_hash, shared_attrs=attrs_as_str
            #     )

            #     state = DBStates(
            #         states_meta_rel=states_meta,
            #         metadata_id=states_meta.metadata_id,
            #         entity_id=states_meta.entity_id,
            #         last_changed_ts=hist_state.ts,
            #         last_updated_ts=hist_state.ts,
            #         state=_stringify_state(entity, hist_state.state),
            #         state_attributes=state_attributes,
            #     )
            #     db_states.append(state)

            # for x in _get_invalid_states(session, entity.entity_id):
            #     session.delete(x)

            # for x in db_states:
            #     session.add(x)

            # return [x.to_native() for x in db_states]

    hass = hass or entity.hass
    hist_states = list(sorted(hist_states, key=lambda x: x.ts))

    rec = get_recorder_instance(hass)
    return await rec.async_add_executor_job(fn, rec, hist_states)


def _build_entity_states_stmt(entity_id: str, *, exclude_invalid=False) -> Select:
    stmt = (
        select(DBStates).join(DBStatesMeta).where(DBStatesMeta.entity_id == entity_id)
    )

    if exclude_invalid:
        stmt = stmt.where(not_(DBStates.state.in_([STATE_UNKNOWN, STATE_UNAVAILABLE])))

    return stmt


def _get_all_states_stmt(entity_id: str) -> Select:
    stmt = (
        select(DBStates).join(DBStatesMeta).where(DBStatesMeta.entity_id == entity_id)
    )

    return stmt


def _get_invalid_states_stmt(entity_id: str) -> Select:
    return (
        select(DBStates)
        .join(DBStatesMeta)
        .where(DBStatesMeta.entity_id == entity_id)
        .where(DBStates.state.in_([STATE_UNKNOWN, STATE_UNAVAILABLE]))
    )


def _get_latest_existing_state(session: Session, entity_id: str) -> DBStates | None:
    stmt = _build_entity_states_stmt(entity_id)
    stmt = stmt.order_by(DBStates.last_updated_ts.desc())

    row = session.execute(stmt).scalar_one_or_none()

    return row


async def run_within_recorder(hass: HomeAssistant, fn, *args, **kwargs) -> Any:
    r = get_recorder_instance(hass)
    return await r.async_add_executor_job(fn, r, *args, **kwargs)


# def with_session(fn, rec: Recorder, *args, **kwargs):
#     with rec.get_session() as session:
#         return fn(session, *args, **kwargs)

# def within_recorder(fn, hass: HomeAssistant, *args, **kwargs):


# def foo(hass: HomeAssistant):
#     def do_a_query(recorder: Recorder, session: Session) -> int:
#         return len(list(session.execute(select(DBStates)).scalars()))

#     return with_session(do_a_query)
