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


def OrderedField(  # noqa: N802, PLR0913
    *args: Any,
    length: int,
    justify: Literal["left", "right"] = "left",
    fill_char: bytes = b" ",
    encoding: str = "utf-8",
    from_str: Callable[[str], Any] = lambda x: x.strip(),
    to_str: Callable[[Any], str] = str,
    **kwargs: Any,
) -> Any:
    """A wrapper for `pydantic.Field` with fixed-width related settings.

    Args:
        args: Positional arguments to be passed to `pydantic.Field`.
        length: The fixed width length of the field.
        justify: Justification of the field content.
        fill_char: Byte used to fill the field.
        encoding: Encoding used for the field.
        from_str: Function to convert from string to the field type.
            If field type is not `str`, user must provide it.
        to_str: Function to convert from the field type to string.
        kwargs: Additional keyword arguments to be passed to `pydantic.Field`.

    Returns:
        A `pydantic.Field` instance with fixed-width related settings.
    """
    global __counter  # noqa: PLW0603

    kwargs.setdefault("json_schema_extra", {})
    field: FieldInfo = Field(*args, **kwargs)

    options = Options(
        field_info=field,
        length=length,
        order=__counter,
        justify=justify,
        fill_char=fill_char,
        encoding=encoding,
        from_str=from_str,
        to_str=to_str,
    )
    options.save()
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
                Options.load(value),
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
            value = getattr(self, field_name)
            s = options.to_str(value)
            b = str.encode(s, options.encoding)
            if len(b) > options.length:
                msg = f"Value of {field_name!r} ({b!r}; length: {len(b)}) is longer than field length {options.length}"
                raise ValueError(msg)

            b = (
                b.ljust(options.length, options.fill_char)
                if options.justify == "left"
                else b.rjust(options.length, options.fill_char)
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
            b = raw[index : index + options.length]
            s = bytes.decode(b, options.encoding)
            value = options.from_str(s)
            values[field_name] = value
            index += options.length

        obj = cls(**values, **extras)
        logger.debug("Parsed %r into %r", raw, obj)

        return obj


_OPTIONS_KEY = "__pydantic_fixedwidth__"
"""Key to store `Options` in `field_info.json_schema_extra`."""


class Options(BaseModel):
    """Options for a fixed-width field."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    field_info: FieldInfo

    length: int
    order: int
    justify: Literal["left", "right"]
    fill_char: bytes = Field(..., min_length=1, max_length=1)
    encoding: str

    from_str: Callable[[str], Any]
    """Callable to create object from a string to the field type."""

    to_str: Callable[[Any], str]
    """Callable to cast the field type to a string."""

    def save(self) -> None:
        """Save `Options` to `field_info`."""
        if not isinstance(self.field_info.json_schema_extra, dict):
            msg = f"`json_schema_extra` must be a `dict`, but got: {type(self.field_info.json_schema_extra)!r}"
            raise TypeError(msg)

        self.field_info.json_schema_extra[_OPTIONS_KEY] = self.model_dump()

    @classmethod
    def load(cls, field_info: FieldInfo) -> Options:
        """Load `Options` from `field_info`."""
        if not isinstance(field_info.json_schema_extra, dict):
            msg = f"`json_schema_extra` must be a `dict`, but got: {type(field_info.json_schema_extra)!r}"
            raise TypeError(msg)

        return cls.model_validate(field_info.json_schema_extra.get(_OPTIONS_KEY, {}))
