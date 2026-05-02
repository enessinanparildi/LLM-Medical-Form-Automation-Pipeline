"""FastAPI dependency providers."""

from typing import Annotated

from fastapi import Depends

from medical_form_automation.config import Settings, get_settings


SettingsDep = Annotated[Settings, Depends(get_settings)]
