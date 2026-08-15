"""CLI argument validation and version wiring."""

from __future__ import annotations

import sys

import pytest

from downloader import parse_arguments
from src import __version__


@pytest.mark.parametrize(
    "option,value",
    [
        ("--max-pages", "0"),
        ("--workers", "0"),
        ("--max-retries", "-1"),
        ("--delay", "-0.1"),
        ("--connections", "0"),
        ("--rate-limit", "0"),
    ],
)
def test_invalid_numeric_options_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    option: str,
    value: str,
) -> None:
    monkeypatch.setattr(sys, "argv", ["buidl", "https://forum.example/thread", option, value])
    with pytest.raises(SystemExit) as error:
        parse_arguments()
    assert error.value.code == 2


def test_version_flag(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["buidl", "--version"])
    with pytest.raises(SystemExit) as error:
        parse_arguments()
    assert error.value.code == 0
    assert __version__ in capsys.readouterr().out
