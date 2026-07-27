"""Typed request bodies for authentication and employee-account mutations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictRequest):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class UserCreateRequest(StrictRequest):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    role: str = "staff"


class UserUpdateRequest(StrictRequest):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    role: str | None = None
    status: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=255)


class UserPasswordChangeRequest(StrictRequest):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)
