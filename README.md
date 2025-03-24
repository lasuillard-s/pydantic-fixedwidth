# pydantic-fixedwidth

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/lasuillard/pydantic-fixedwidth/actions/workflows/ci.yaml/badge.svg)](https://github.com/lasuillard/pydantic-fixedwidth/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/gh/lasuillard/pydantic-fixedwidth/graph/badge.svg?token=R5pQWB43DP)](https://codecov.io/gh/lasuillard/pydantic-fixedwidth)
![PyPI - Version](https://img.shields.io/pypi/v/pydantic-fixedwidth)

Custom Pydantic models for serializing and deserializing fixed-width format data.


## 🚀 Quick Start

Install this package with pip:

```shell
$ pip install pydantic-fixedwidth
```

Usage example:

```python
from datetime import datetime, timezone

from pydantic_fixedwidth import Fixedwidth, Padding
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


some_request = SomeRequest(
    string="<DFG&",
    hangul="한글",
    number=381,
    ts=datetime(2024, 1, 23, 14, 11, 20, 124277, tzinfo=tzinfo),
)
b = some_request.format_bytes()

assert len(b) == 54
assert b == b"<DFG&   \xed\x95\x9c\xea\xb8\x800000000381          20240123141120124277"
```
