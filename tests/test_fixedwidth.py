from datetime import UTC, datetime
from typing import Annotated

import pydantic
import pytest

from pydantic_fixedwidth import Fixedwidth, Options, Padding
from pydantic_fixedwidth import OrderedField as Field

tzinfo = UTC


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


class Header(Fixedwidth):
    version: int = Field(length=2, justify="right", fill_char=b"0", from_str=int)
    kind: str = Field(length=4)


class ExtendedHeader(Fixedwidth):
    version: int = Field(length=2, justify="right", fill_char=b"0", from_str=int)
    kind: str = Field(length=4)
    flags: str = Field(length=2)


class Address(Fixedwidth):
    city: str = Field(length=6)
    zipcode: str = Field(length=5)


class TestNestedFixedwidth:
    def test_nested_round_trip(self) -> None:
        class Packet(Fixedwidth):
            prefix: str = Field(length=2)
            header: Header
            p_: str = Padding(length=2)
            suffix: str = Field(length=3)

        packet = Packet(prefix=">>", header=Header(version=1, kind="REQ"), suffix="END")
        raw = packet.format_bytes()

        assert len(raw) == 13
        assert raw == b">>01REQ   END"
        assert Packet.parse_bytes(raw) == packet
        assert (
            Packet.model_validate({"prefix": ">>", "header": {"version": 1, "kind": "REQ"}, "suffix": "END"}) == packet
        )

    def test_multi_level_and_repeated_nested_models(self) -> None:
        class Customer(Fixedwidth):
            name: str = Field(length=6)
            billing: Address
            shipping: Address

        class Order(Fixedwidth):
            order_id: int = Field(length=4, justify="right", fill_char=b"0", from_str=int)
            customer: Customer
            status: str = Field(length=4)

        order = Order(
            order_id=42,
            customer=Customer(
                name="Alice",
                billing=Address(city="Seoul", zipcode="12345"),
                shipping=Address(city="Busan", zipcode="67890"),
            ),
            status="PAID",
        )
        raw = order.format_bytes()

        assert len(raw) == 36
        assert raw == b"0042Alice Seoul 12345Busan 67890PAID"
        assert Order.parse_bytes(raw) == order

    def test_nested_diamond_hierarchy_round_trip(self) -> None:
        class Leaf(Fixedwidth):
            code: str = Field(length=2)

        class LeftBranch(Fixedwidth):
            leaf: Leaf
            tag: str = Field(length=1)

        class RightBranch(Fixedwidth):
            leaf: Leaf
            tag: str = Field(length=1)

        class Root(Fixedwidth):
            left: LeftBranch
            right: RightBranch

        root = Root(
            left=LeftBranch(leaf=Leaf(code="L1"), tag="A"),
            right=RightBranch(leaf=Leaf(code="R2"), tag="B"),
        )
        raw = root.format_bytes()

        assert raw == b"L1AR2B"
        assert Root.parse_bytes(raw) == root

    def test_nested_mixed_encodings(self) -> None:
        class InnerUtf8(Fixedwidth):
            hangul: str = Field(length=6)

        class OuterMixed(Fixedwidth):
            binary_tag: str = Field(length=2, encoding="latin-1")
            inner: InnerUtf8
            tail: str = Field(length=2, encoding="ascii")

        model = OuterMixed(binary_tag="\xff\xfe", inner=InnerUtf8(hangul="한글"), tail="OK")
        raw = model.format_bytes()

        assert raw == b"\xff\xfe\xed\x95\x9c\xea\xb8\x80OK"
        assert OuterMixed.parse_bytes(raw) == model

    def test_nested_pydantic_field_annotated_and_exclude(self) -> None:
        class Meta(Fixedwidth):
            tag: str = Field(length=4)

        class Envelope(Fixedwidth):
            meta: Meta = pydantic.Field(
                default_factory=lambda: Meta(tag="DFLT"),
                json_schema_extra={"description": "default meta"},
            )
            annotated_meta: Annotated[Meta, pydantic.Field(description="annotated")]
            ignored: Meta = pydantic.Field(default_factory=lambda: Meta(tag="SKIP"), exclude=True)

        env = Envelope(annotated_meta=Meta(tag="REAL"))
        raw = env.format_bytes()

        assert len(raw) == 8
        assert raw == b"DFLTREAL"
        assert Envelope.parse_bytes(raw) == env
        assert Envelope.parse_bytes(raw, ignored=Meta(tag="OVRD")).ignored == Meta(tag="OVRD")

    def test_nested_inheritance_preserves_fields(self) -> None:
        class BasePacket(Fixedwidth):
            header: Header
            tail: str = Field(length=2)

        class ExtendedPacket(BasePacket):
            checksum: str = Field(length=4)

        ext = ExtendedPacket(header=Header(version=2, kind="ACK"), tail="OK", checksum="ABCD")
        raw = ext.format_bytes()

        assert len(raw) == 12
        assert raw == b"02ACK OKABCD"
        assert ExtendedPacket.parse_bytes(raw) == ext

    def test_nested_field_override_preserves_declaration_order(self) -> None:
        class BasePacket(Fixedwidth):
            header: Header
            tail: str = Field(length=2)

        class OverriddenPacket(BasePacket):
            header: ExtendedHeader  # type: ignore[assignment]

        ovrd = OverriddenPacket(header=ExtendedHeader(version=3, kind="SYN", flags="FF"), tail="OK")
        raw = ovrd.format_bytes()

        assert len(raw) == 10
        assert raw == b"03SYN FFOK"
        assert OverriddenPacket.parse_bytes(raw) == ovrd

    def test_scalar_field_override_preserves_declaration_order(self) -> None:
        class BaseRecord(Fixedwidth):
            first: str = Field(length=2)
            second: str = Field(length=2)

        class ChildRecord(BaseRecord):
            first: str = Field(length=4)

        record = ChildRecord(first="ABCD", second="XY")
        raw = record.format_bytes()

        assert raw == b"ABCDXY"
        assert ChildRecord.parse_bytes(raw) == record

    def test_nested_empty_model(self) -> None:
        class Empty(Fixedwidth):
            pass

        class Wrapper(Fixedwidth):
            empty: Empty
            code: str = Field(length=3)

        wrapper = Wrapper(empty=Empty(), code="XYZ")
        raw = wrapper.format_bytes()

        assert len(raw) == 3
        assert raw == b"XYZ"
        assert Wrapper.parse_bytes(raw) == wrapper

    def test_nested_ordered_field_rejected(self) -> None:
        with pytest.raises(TypeError, match="Nested Fixedwidth field 'header' must not use `OrderedField`"):

            class _InvalidParent(Fixedwidth):
                header: Header = Field(length=6)

    def test_nested_annotated_ordered_field_rejected(self) -> None:
        with pytest.raises(TypeError, match="Nested Fixedwidth field 'header' must not use `OrderedField`"):

            class _InvalidAnnotatedParent(Fixedwidth):
                header: Annotated[Header, Field(length=6)]

    def test_nested_longer_subclass_rejected_on_format_bytes(self) -> None:
        class Packet(Fixedwidth):
            header: Header
            tail: str = Field(length=2)

        class LongerHeader(Header):
            flags: str = Field(length=2)

        longer_packet = Packet(header=LongerHeader(version=1, kind="REQ", flags="FF"), tail="OK")
        with pytest.raises(
            ValueError,
            match=r"Value of 'header' \(b'01REQ FF'; length: 8\) does not match field length 6",
        ):
            longer_packet.format_bytes()

    def test_nested_shorter_subclass_rejected_on_format_bytes(self) -> None:
        class Packet(Fixedwidth):
            header: Header
            tail: str = Field(length=2)

        class ShorterHeader(Header):
            kind: str = Field(length=4, exclude=True)

        shorter_packet = Packet(header=ShorterHeader(version=1, kind="REQ"), tail="OK")
        with pytest.raises(
            ValueError,
            match=r"Value of 'header' \(b'01'; length: 2\) does not match field length 6",
        ):
            shorter_packet.format_bytes()

    def test_nested_mutated_non_model_rejected_on_format_bytes(self) -> None:
        class Packet(Fixedwidth):
            header: Header
            tail: str = Field(length=2)

        mutated_packet = Packet(header=Header(version=1, kind="REQ"), tail="OK")
        mutated_packet.header = "not-a-header"  # type: ignore[assignment]
        with pytest.raises(TypeError, match="Value of 'header' must be an instance of 'Header', got <class 'str'>"):
            mutated_packet.format_bytes()

    def test_nested_scalar_overflow_propagates_on_format_bytes(self) -> None:
        class Packet(Fixedwidth):
            header: Header
            tail: str = Field(length=2)

        packet = Packet(header=Header(version=1, kind="TOO-LONG"), tail="OK")
        with pytest.raises(
            ValueError,
            match=r"Value of 'kind' \(b'TOO-LONG'; length: 8\) is longer than field length 4",
        ):
            packet.format_bytes()

    def test_nested_forward_reference_and_model_rebuild(self) -> None:
        class ForwardOuter(Fixedwidth):
            prefix: str = Field(length=2)
            inner: "ForwardInner"
            suffix: str = Field(length=2)

        assert not ForwardOuter.__pydantic_complete__
        assert ForwardOuter.model_rebuild(raise_errors=False) is False

        with pytest.raises(TypeError, match="Model 'ForwardOuter' is not fully defined"):
            ForwardOuter.parse_bytes(b"AB0042CD")

        class ForwardInner(Fixedwidth):
            value: int = Field(length=4, justify="right", fill_char=b"0", from_str=int)

        assert ForwardOuter.model_rebuild() is True

        obj = ForwardOuter(prefix="AB", inner=ForwardInner(value=42), suffix="CD")
        raw = obj.format_bytes()
        assert len(raw) == 8
        assert raw == b"AB0042CD"
        assert ForwardOuter.parse_bytes(raw) == obj

    def test_nested_transitive_forward_reference(self) -> None:
        class Outer(Fixedwidth):
            middle: "Middle"

        class Middle(Fixedwidth):
            leaf: "Leaf"

        class Leaf(Fixedwidth):
            val: str = Field(length=4)

        assert Middle.model_rebuild() is True
        assert Outer.model_rebuild() is True

        obj = Outer(middle=Middle(leaf=Leaf(val="test")))
        raw = obj.format_bytes()
        assert len(raw) == 4
        assert raw == b"test"
        assert Outer.parse_bytes(raw) == obj

    def test_nested_deferred_submodel_rebuild(self) -> None:
        class DeferredInner(Fixedwidth):
            leaf: "DeferredLeaf"

        class DeferredOuter(Fixedwidth):
            inner: DeferredInner

        with pytest.raises(TypeError, match="Model 'DeferredOuter' is not fully defined"):
            DeferredOuter.parse_bytes(b"ABCD")

        class DeferredLeaf(Fixedwidth):
            val: str = Field(length=4)

        assert DeferredInner.model_rebuild() is True
        assert DeferredOuter.model_rebuild() is True

        parsed = DeferredOuter.parse_bytes(b"ABCD")
        assert parsed == DeferredOuter(inner=DeferredInner(leaf=DeferredLeaf(val="ABCD")))
        assert parsed.format_bytes() == b"ABCD"

    def test_nested_self_recursive_model_rejected(self) -> None:
        with pytest.raises(ValueError, match="Circular nested Fixedwidth model is not supported: '_SelfRecursive'"):

            class _SelfRecursive(Fixedwidth):
                name: str = Field(length=4)
                nxt: "_SelfRecursive"

    def test_nested_incomplete_submodel_rejected_on_parse_bytes(self) -> None:
        class CycleA(Fixedwidth):
            b: "CycleB"

        class CycleB(Fixedwidth):
            a: CycleA

        class CycleHolder(Fixedwidth):
            b: CycleB

        with pytest.raises(TypeError, match="Nested Fixedwidth model 'CycleA' is not fully defined"):
            CycleHolder.parse_bytes(b"")

    def test_nested_indirect_circular_model_rejected(self) -> None:
        class CycleA(Fixedwidth):
            b: "_CycleB"

        class _CycleB(Fixedwidth):
            a: CycleA

        with pytest.raises(ValueError, match="Circular nested Fixedwidth model is not supported"):
            CycleA.model_rebuild()
