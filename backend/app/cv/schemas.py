"""The shape of a CV: sections a person fills in, one version per target role."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

Short = Field(default="", max_length=120)

#: Characters XML 1.0 cannot hold at all (most C0 controls, lone surrogates,
#: U+FFFE/U+FFFF). A CV containing one would make a Word file no program opens.
#: Tab, line feed and carriage return are allowed.
XML_INVALID = re.compile("[^\t\n\r\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def xml_safe(text: str) -> str:
    return XML_INVALID.sub("", text)


def _strip_invalid(value):
    if isinstance(value, str):
        return xml_safe(value)
    if isinstance(value, list):
        return [xml_safe(v) if isinstance(v, str) else v for v in value]
    return value


class _Clean(BaseModel):
    """Removes characters XML cannot hold from every text field, before the
    length and list checks run."""

    @field_validator("*", mode="before")
    @classmethod
    def _xml(cls, value):
        return _strip_invalid(value)


def _clean(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item and item.strip()]


class Role(_Clean):
    title: str = Short
    organisation: str = Short
    place: str = Short
    start: str = Field(default="", max_length=30)
    end: str = Field(default="", max_length=30)
    bullets: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("bullets")
    @classmethod
    def _bullets(cls, value: list[str]) -> list[str]:
        value = _clean(value)
        if any(len(b) > 300 for b in value):
            raise ValueError("Keep each bullet under 300 characters")
        return value


class Study(_Clean):
    qualification: str = Short
    institution: str = Short
    start: str = Field(default="", max_length=30)
    end: str = Field(default="", max_length=30)
    note: str = Field(default="", max_length=300)


class CvData(_Clean):
    name: str = Short
    headline: str = Short
    email: str = Short
    phone: str = Field(default="", max_length=40)
    location: str = Short
    links: list[str] = Field(default_factory=list, max_length=4)
    summary: str = Field(default="", max_length=1200)
    experience: list[Role] = Field(default_factory=list, max_length=12)
    education: list[Study] = Field(default_factory=list, max_length=6)
    skills: list[str] = Field(default_factory=list, max_length=40)
    languages: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("links", "skills", "languages")
    @classmethod
    def _items(cls, value: list[str]) -> list[str]:
        value = _clean(value)
        if any(len(v) > 120 for v in value):
            raise ValueError("Keep each item under 120 characters")
        return value


class CvIn(_Clean):
    title: str = Field(min_length=1, max_length=120)
    target_role: str | None = Field(default=None, max_length=120)
    data: CvData = Field(default_factory=CvData)

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class CvCopy(_Clean):
    title: str = Field(min_length=1, max_length=120)
    target_role: str | None = Field(default=None, max_length=120)
