"""Dùng chung cho các file kiểm thử: đường dẫn đề mẫu, kho mẫu."""
import os

import pytest

from nganhangde.db import Bank
from nganhangde.parser import parse_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "0-1-De-chuan-hoa-1.tex")


@pytest.fixture
def bank(tmp_path):
    b = Bank(str(tmp_path / "t.db"))
    for q in parse_file(SAMPLE):
        b.add(q)
    yield b
    b.close()
