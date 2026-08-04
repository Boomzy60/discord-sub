import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    discord_id: str
    username: str
    global_name: str | None
    avatar: str | None
    email: str | None
    is_admin: bool
    created_at: datetime
