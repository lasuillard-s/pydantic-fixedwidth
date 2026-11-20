# pydantic-fixedwidth

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![codecov](https://codecov.io/gh/lasuillard-s/pydantic-fixedwidth/graph/badge.svg?token=R5pQWB43DP)](https://codecov.io/gh/lasuillard-s/pydantic-fixedwidth)
[![PyPI - Version](https://img.shields.io/pypi/v/pydantic-fixedwidth)](https://pypi.org/project/pydantic-fixedwidth/)

Custom Pydantic models for serializing and deserializing fixed-width data.

## ✨ Features

This small Python package provides tools for working with fixed-width data and for serializing and deserializing it using Pydantic models.

## 🚀 Quick Start

Install this package with pip:

```shell
$ pip install pydantic-fixedwidth
```

Usage example:

```python
from datetime import datetime, timezone

from pydantic_fixedwidth import Fixedwidth, Padding
from pydantic_fixedwidth import FixedwidthField as Field

tzinfo = timezone.utc


class Header(Fixedwidth):
    version: int = Field(length=2, justify="right", fill_char=b"0")
    kind: str = Field(length=4)


class SomeRequest(Fixedwidth):
    header: Header
    string: str = Field(length=8)
    hangul: str = Field(length=6)
    number: int = Field(length=10, justify="right", fill_char=b"0")

    # Just a padding field
    p_: str = Padding(length=10)

    # This field will be ignored in ser/de
    ignore: str = Field(length=10, default="IGNORE", exclude=True)

    ts: datetime = Field(
        length=20,
        to_str=lambda dt: dt.strftime("%Y%m%d%H%M%S%f"),
        from_str=lambda s: datetime.strptime(s, "%Y%m%d%H%M%S%f").replace(tzinfo=tzinfo),
    )


# Format model to bytes
some_request = SomeRequest(
    header=Header(version=1, kind="REQ"),
    string="<DFG&",
    hangul="한글",
    number=381,
    ts=datetime(2024, 1, 23, 14, 11, 20, 124277, tzinfo=tzinfo),
)
b = some_request.format_bytes()

assert len(b) == 60
assert b == b"01REQ <DFG&   \xed\x95\x9c\xea\xb8\x800000000381          20240123141120124277"

# Parse bytes into model
parsed_request = SomeRequest.parse_bytes(b)

assert parsed_request == some_request
```

## 💖 Contributing

Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for information on contributing to this project.

## 📜 License

This project is licensed under the MIT License.
