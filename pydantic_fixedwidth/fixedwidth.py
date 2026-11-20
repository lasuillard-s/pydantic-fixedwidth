# noqa: D100
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Any, ClassVar, Literal, Self

from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo  # noqa: TC002

logger = logging.getLogger(__name__)


def FixedwidthField(  # noqa: N802, PLR0913
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
    field: FieldInfo = Field(*args, **kwargs)

    options = Options(
        length=length,
        justify=justify,
        fill_char=fill_char,
        encoding=encoding,
        from_str=from_str,
        to_str=to_str,
    )
    field.metadata.append(_OptionsMarker(options))

    return field


# Shortcuts for convenience
Padding = partial(FixedwidthField, default="")


@dataclass(frozen=True, slots=True)
class _OptionsMarker:
    """Internal wrapper storing `Options` inside `FieldInfo.metadata` without Pydantic schema hooks."""

    options: Options


@dataclass(frozen=True, slots=True)
class _NestedField:
    """Metadata for a nested `Fixedwidth` model field."""

    model: type[Fixedwidth]
    length: int


class Fixedwidth(BaseModel):
    """A base class for fixed-width models."""

    _field_options: ClassVar[dict[str, Options | _NestedField]] = {}
    _total_length: ClassVar[int] = 0
    _fields_initialized_for: ClassVar[type[Fixedwidth] | None] = None

    @classmethod
    def __pydantic_init_subclass__(cls, *args: Any, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(*args, **kwargs)
        cls._init_fixedwidth_fields(strict=False)

    @classmethod
    def model_rebuild(cls, *args: Any, **kwargs: Any) -> bool | None:
        """Rebuild the model schema and refresh fixed-width field metadata."""
        kwargs["_parent_namespace_depth"] = kwargs.get("_parent_namespace_depth", 2) + 1
        rebuilt = super().model_rebuild(*args, **kwargs)
        if cls.__pydantic_complete__:
            cls._init_fixedwidth_fields(strict=False)

        return rebuilt

    @classmethod
    def _set_fixedwidth_fields(
        cls,
        fields: dict[str, Options | _NestedField] | None = None,
        total_length: int = 0,
    ) -> None:
        if fields is None:
            cls._field_options = {}
            cls._total_length = 0
            cls._fields_initialized_for = None
            return

        cls._field_options = fields
        cls._total_length = total_length
        cls._fields_initialized_for = cls

    @classmethod
    def _assert_no_cycle(
        cls,
        model: type[Fixedwidth],
        visited: frozenset[type[Fixedwidth]],
        checked: set[type[Fixedwidth]],
    ) -> None:
        if model in visited:
            msg = f"Circular nested Fixedwidth model is not supported: {cls.__name__!r}"
            raise ValueError(msg)
        if model in checked:
            return

        next_visited = visited | {model}
        for spec in model._field_options.values():  # noqa: SLF001
            if isinstance(spec, _NestedField):
                cls._assert_no_cycle(spec.model, next_visited, checked)

        checked.add(model)

    @classmethod
    def _resolve_field_spec(
        cls,
        field_name: str,
        field_info: FieldInfo,
        visited: frozenset[type[Fixedwidth]],
        checked: set[type[Fixedwidth]],
        *,
        strict: bool,
    ) -> Options | _NestedField | None:
        annotation = field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, Fixedwidth):
            if any(isinstance(item, _OptionsMarker) for item in field_info.metadata):
                msg = f"Nested Fixedwidth field {field_name!r} must not use `FixedwidthField`"
                raise TypeError(msg)

            cls._assert_no_cycle(annotation, visited, checked)
            if not annotation.__pydantic_complete__:
                if strict:
                    msg = f"Nested Fixedwidth model {annotation.__name__!r} is not fully defined"
                    raise TypeError(msg)
                return None

            if (
                annotation._fields_initialized_for is not annotation  # noqa: SLF001
                and not annotation._init_fixedwidth_fields(visited, checked=checked, strict=strict)  # noqa: SLF001
            ):
                return None

            return _NestedField(model=annotation, length=annotation._total_length)  # noqa: SLF001

        return Options.load(field_info)

    @classmethod
    def _init_fixedwidth_fields(
        cls,
        _visited: frozenset[type[Fixedwidth]] = frozenset(),
        *,
        checked: set[type[Fixedwidth]] | None = None,
        strict: bool = True,
    ) -> bool:
        if not cls.__pydantic_complete__:
            cls._set_fixedwidth_fields()
            if strict:
                msg = f"Model {cls.__name__!r} is not fully defined; call `{cls.__name__}.model_rebuild()` first."
                raise TypeError(msg)

            return False

        visited = _visited | {cls}
        active_checked = set() if checked is None else checked
        fields: dict[str, Options | _NestedField] = {}
        total_length = 0
        deferred = False
        for key, value in cls.model_fields.items():
            if value.exclude:
                continue

            spec = cls._resolve_field_spec(key, value, visited, active_checked, strict=strict)
            if spec is None:
                deferred = True
                continue

            fields[key] = spec
            total_length += spec.length

        if deferred:
            cls._set_fixedwidth_fields()
            return False

        cls._set_fixedwidth_fields(fields, total_length)
        return True

    @classmethod
    def _ensure_initialized(cls) -> None:
        if cls._fields_initialized_for is not cls:
            cls._init_fixedwidth_fields(strict=True)

    @staticmethod
    def _format_field(field_name: str, value: Any, spec: Options | _NestedField) -> bytes:
        if isinstance(spec, _NestedField):
            if not isinstance(value, spec.model):
                msg = f"Value of {field_name!r} must be an instance of {spec.model.__name__!r}, got {type(value)!r}"
                raise TypeError(msg)

            formatted: bytes = value.format_bytes()
            if len(formatted) != spec.length:
                msg = (
                    f"Value of {field_name!r} ({formatted!r}; length: {len(formatted)}) "
                    f"does not match field length {spec.length}"
                )
                raise ValueError(msg)

            return formatted

        s = spec.to_str(value)
        b = str.encode(s, spec.encoding)
        if len(b) > spec.length:
            msg = f"Value of {field_name!r} ({b!r}; length: {len(b)}) is longer than field length {spec.length}"
            raise ValueError(msg)

        return b.ljust(spec.length, spec.fill_char) if spec.justify == "left" else b.rjust(spec.length, spec.fill_char)

    def format_bytes(self) -> bytes:
        """Format the model as a fixed-width byte string."""
        self._ensure_initialized()
        values = [
            self._format_field(field_name, getattr(self, field_name), spec)
            for field_name, spec in self._field_options.items()
        ]
        result = b"".join(values)
        logger.debug("Formatted %r into %r", self, result)

        return result

    @staticmethod
    def _parse_field(
        raw_slice: bytes,
        field_name: str,
        spec: Options | _NestedField,
        extras: dict[str, Any],
    ) -> Any:
        if isinstance(spec, Options):
            return spec.from_str(bytes.decode(raw_slice, spec.encoding))

        if field_name not in extras:
            return spec.model.parse_bytes(raw_slice)

        nested_extras = extras.pop(field_name)
        if not isinstance(nested_extras, Mapping):
            msg = f"Extras for nested field {field_name!r} must be a mapping, got {type(nested_extras)!r}"
            raise TypeError(msg)

        return spec.model.parse_bytes(raw_slice, **nested_extras)

    @classmethod
    def parse_bytes(cls, raw: bytes, **extras: Any) -> Self:
        """Parse a fixed-width byte string into a model.

        For nested `Fixedwidth` fields, passing a mapping under the nested field's name in
        `extras` forwards those keyword arguments to that nested model's `parse_bytes`.
        """
        cls._ensure_initialized()

        values: dict[str, Any] = {}
        index = 0
        for field_name, spec in cls._field_options.items():
            b = raw[index : index + spec.length]
            values[field_name] = cls._parse_field(b, field_name, spec, extras)
            index += spec.length

        obj = cls(**values, **extras)
        logger.debug("Parsed %r into %r", raw, obj)

        return obj


class Options(BaseModel):
    """Options for a fixed-width field."""

    length: int
    justify: Literal["left", "right"]
    fill_char: bytes = Field(..., min_length=1, max_length=1)
    encoding: str

    from_str: Callable[[str], Any]
    """Callable to create object from a string to the field type."""

    to_str: Callable[[Any], str]
    """Callable to cast the field type to a string."""

    @classmethod
    def load(cls, field_info: FieldInfo) -> Options:
        """Load `Options` from `field_info`."""
        matches = [item.options for item in field_info.metadata if isinstance(item, _OptionsMarker)]
        if not matches:
            msg = "Fixedwidth field options not found on field metadata"
            raise TypeError(msg)

        if len(matches) > 1:
            msg = "Multiple Fixedwidth field options found on a single field"
            raise ValueError(msg)

        return matches[0]
