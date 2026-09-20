"""Timezone-aware response timestamps for persisted UTC values.

SQLite drops tzinfo on read. Outgoing records must retain their actual instant
instead of letting each client interpret a naive timestamp in its local zone.
Do not use this type for user-entered wall times, which use deadline_to_utc.
"""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator

from app.time import as_utc

UtcDateTime = Annotated[datetime, AfterValidator(as_utc)]
