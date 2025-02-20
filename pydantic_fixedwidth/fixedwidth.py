# noqa: D100
from __future__ import annotations

import logging
from collections import OrderedDict
from functools import partial
from typing import Any, Callable, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo  # noqa: TC002
from typing_extensions import Self

logger = logging.getLogger(__name__)


__counter = 0


def OrderedField(*args: Any, **kwargs: Any) -> Any:  # noqa: N802
    """An wrapper for`pydantic.Field` with fixed-width related settings."""
    global __counter  # noqa: PLW0603

    field: FieldInfo = Field(*args, **kwargs)
    if not field.exclude:
        config = {
            "field_info": field,
            "order": __counter,
            **{key: value for key, value in kwargs.items() if key in Options.model_fields},
        }
        options: Options = Options.model_validate(config)
        options.save_to(field)

        __counter += 1

    return field


# Shortcuts for convenience
Padding = partial(OrderedField, default="")


class Fixedwidth(BaseModel):
    """A base class for fixed-width models."""

    _field_options: ClassVar[OrderedDict[str, Options]]

    @classmethod
    def __pydantic_init_subclass__(cls, *args: Any, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(*args, **kwargs)

        field_options = (
            (
                key,
                Options.load_from(value),
            )
            for key, value in cls.model_fields.items()
            if not value.exclude
        )

        sorted_by_order = sorted(field_options, key=lambda x: x[1].order)
        cls._field_options = OrderedDict(sorted_by_order)

    def format_bytes(self) -> bytes:
        """Format the model as a fixed-width byte string."""
        values: list[bytes] = []
        for field_name, options in self._field_options.items():
            if options.field_info.exclude:
                continue

            value = getattr(self, field_name)
            s = options.to_str(value)
            b = options.to_bytes(s, options.encoding)
            if len(b) > options.length:
                msg = f"Value of {field_name!r} ({b!r}; length: {len(b)}) is longer than field length {options.length}"
                raise ValueError(msg)

            b = (
                b.ljust(options.length, options.fill_byte)
                if options.justify == "left"
                else b.rjust(options.length, options.fill_byte)
            )
            values.append(b)

        result = b"".join(values)
        logger.debug("Formatted %r into %r", self, result)

        return result

    @classmethod
    def parse_bytes(cls, raw: bytes, **extras: Any) -> Self:
        """Parse a fixed-width byte string into a model."""
        values: dict[str, Any] = {}
        index = 0
        for field_name, options in cls._field_options.items():
            if options.field_info.exclude:
                continue

            b = raw[index : index + options.length]
            s = options.from_bytes(b, options.encoding)
            value = options.from_str(s)
            values[field_name] = value
            index += options.length

        obj = cls(**values, **extras)
        logger.debug("Parsed %r into %r", raw, obj)

        return obj


class Options(BaseModel):
    """Options for a fixed-width field."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    field_info: FieldInfo
    length: int
    order: int

    justify: Literal["left", "right"] = "left"
    fill_byte: bytes = Field(b" ", min_length=1, max_length=1)
    encoding: str = "utf-8"

    from_str: Callable[[str], Any] = lambda x: x.strip()
    """Callable to create object from a string to the field type.

    if field type is not `str`, this must be provided by user.
    """

    to_str: Callable[[Any], str] = str
    """Callable to cast the field type to a string."""

    from_bytes: Callable[[bytes, str], str] = bytes.decode
    to_bytes: Callable[[str, str], bytes] = str.encode

    def save_to(self, field_info: FieldInfo) -> None:
        """Save `Options` to `field_info`."""
        if not isinstance(field_info.json_schema_extra, dict):
            msg = "`field_info.json_schema_extra` must be a `dict`"
            raise TypeError(msg)

        field_info.json_schema_extra.update(self.model_dump())

    @classmethod
    def load_from(cls, field_info: FieldInfo) -> Options:
        """Load `Options` from `field_info`."""
        if not isinstance(field_info.json_schema_extra, dict):
            msg = f"`field_info.json_schema_extra` must be a `dict`: {field_info}"
            raise TypeError(msg)

        return cls.model_validate(field_info.json_schema_extra)
