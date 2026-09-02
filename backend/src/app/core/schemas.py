from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema for all Pydantic models: read from ORM attributes, strip string whitespace."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
    )
