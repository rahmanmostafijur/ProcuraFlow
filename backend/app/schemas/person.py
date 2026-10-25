from pydantic import BaseModel, ConfigDict


class PersonRead(BaseModel):
    """Just enough to name someone on a document: no email, role or permissions."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
