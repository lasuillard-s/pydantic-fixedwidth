from datetime import datetime, timezone

import pydantic
import pytest

from pydantic_fixedwidth import Fixedwidth, Options, Padding
from pydantic_fixedwidth import OrderedField as Field

tzinfo = timezone.utc


class SomeRequest(Fixedwidth):
    string: str = Field(length=8)
    hangul: str = Field(length=6)
    number: int = Field(length=10, justify="right", fill_char=b"0")

    # Just an padding field
    p_: str = Padding(length=10)

    # This field will be ignored in ser/de
    ignore: str = Field(length=10, default="IGNORE", exclude=True)

    ts: datetime = Field(
        length=20,
        to_str=lambda dt: dt.strftime("%Y%m%d%H%M%S%f"),
        from_str=lambda s: datetime.strptime(s, "%Y%m%d%H%M%S%f").replace(tzinfo=tzinfo),
    )


class TestFixedwidth:
    def test_format_bytes(self) -> None:
        some_request = SomeRequest(
            string="<DFG&",
            hangul="한글",
            number=381,
            ts=datetime(2024, 1, 23, 14, 11, 20, 124277, tzinfo=tzinfo),
        )
        b = some_request.format_bytes()

        assert len(b) == 54
        assert b == b"<DFG&   \xed\x95\x9c\xea\xb8\x800000000381          20240123141120124277"

    def test_format_bytes_too_long(self) -> None:
        some_request = SomeRequest(
            string="<DFG&",
            hangul="한글",
            number=381,
            ts=datetime(2024, 1, 23, 14, 11, 20, 124277, tzinfo=tzinfo),
        )

        # This should raise an exception
        some_request.string = "very-long-string"
        with pytest.raises(
            ValueError,
            match=r"Value of 'string' \(b'very-long-string'; length: 16\) is longer than field length 8",
        ):
            some_request.format_bytes()

    def test_parse_bytes(self) -> None:
        b = b"<DFG&   \xed\x95\x9c\xea\xb8\x800000000381          20240123141120124277"
        some_request = SomeRequest.parse_bytes(b)

        assert some_request == SomeRequest(
            string="<DFG&",
            hangul="한글",
            number=381,
            ts=datetime(2024, 1, 23, 14, 11, 20, 124277, tzinfo=tzinfo),
        )


class TestOptions:
    def test_save_json_schema_extra_is_not_dict(self) -> None:
        with pytest.raises(TypeError, match="`json_schema_extra` must be a `dict`, but got: <class 'str'>"):
            Field(length=10, json_schema_extra="not-a-dict")

    def test_load_json_schema_extra_is_not_dict(self) -> None:
        field = pydantic.Field()
        with pytest.raises(TypeError, match="`json_schema_extra` must be a `dict`, but got: <class 'NoneType'>"):
            Options.load(field)
