from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class Envelope(BaseModel):
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)
    results: list[object]


class PersonDTO(BaseModel):
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)
    id: Annotated[int, Field(strict=True, gt=0)]
    name: StrictStr
    known_for_department: object = None
    profile_path: object = None
    known_for: object = None
