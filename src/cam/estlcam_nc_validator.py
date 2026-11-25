"""Conservative validator for the SurfWing CAD Estlcam UNO XYZ MVP.

This is a project-side static checker, not an Estlcam emulator and not a
machine-safety system. It deliberately supports only explicit G00/G01 moves.
Units and work zero are configured in Estlcam and cannot be inferred safely
from this NC dialect; the caller must supply the expected unit and envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Mapping


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
_TOKEN_RE = re.compile(rf"([A-Za-z])({_NUMBER})")
_ALLOWED_WORDS = {"N", "G", "X", "Y", "Z", "F", "S"}
_SUPPORTED_MOTION = {"0", "00", "1", "01"}


@dataclass(frozen=True)
class AxisLimit:
    minimum: float
    maximum: float


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    motion_lines: int = 0
    final_position: dict[str, float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


class EstlcamNCValidator:
    """Fail-closed checker for a deliberately restricted Estlcam NC subset."""

    def __init__(self, *, expected_unit: str | None = None,
                 axis_limits: Mapping[str, AxisLimit] | None = None,
                 allow_arcs: bool = False, allow_spindle_words: bool = False) -> None:
        if expected_unit not in (None, "mm", "inch"):
            raise ValueError("expected_unit must be 'mm', 'inch', or None")
        self.expected_unit = expected_unit
        self.axis_limits = dict(axis_limits or {})
        self.allow_arcs = allow_arcs
        self.allow_spindle_words = allow_spindle_words

    @staticmethod
    def _strip_comment(line: str) -> str:
        if line.count("(") != line.count(")") or line.count("(") > 1:
            raise ValueError("malformed or nested parenthesized comment")
        return re.sub(r"\([^()]*\)", "", line).strip()

    def validate(self, program: str) -> ValidationReport:
        report = ValidationReport()
        position: dict[str, float] = {}
        if not program.strip():
            report.errors.append("NC program is empty")
            return report

        for line_no, raw in enumerate(program.splitlines(), start=1):
            try:
                line = self._strip_comment(raw)
            except ValueError as exc:
                report.errors.append(f"line {line_no}: {exc}")
                continue
            if not line:
                continue
            tokens: list[tuple[str, str]] = []
            cursor = 0
            for match in _TOKEN_RE.finditer(line):
                if line[cursor:match.start()].strip():
                    report.errors.append(f"line {line_no}: invalid text or unsupported syntax near {line[cursor:match.start()]!r}")
                    tokens = []
                    break
                tokens.append((match.group(1).upper(), match.group(2)))
                cursor = match.end()
            else:
                if line[cursor:].strip():
                    report.errors.append(f"line {line_no}: trailing invalid syntax")
                    continue
            if not tokens:
                continue
            words: dict[str, list[str]] = {}
            for letter, value in tokens:
                if letter not in _ALLOWED_WORDS:
                    report.errors.append(f"line {line_no}: unsupported address {letter}")
                    continue
                words.setdefault(letter, []).append(value)
            if any(len(values) > 1 for values in words.values()):
                report.errors.append(f"line {line_no}: duplicate address word")
                continue
            if "N" in words and not words["N"][0].isdigit():
                report.errors.append(f"line {line_no}: line number N must be an integer")
            if "S" in words and not self.allow_spindle_words:
                report.errors.append(f"line {line_no}: spindle word S disabled in draft machine profile")
            if "F" in words:
                feed = float(words["F"][0])
                if not math.isfinite(feed) or feed <= 0:
                    report.errors.append(f"line {line_no}: feed F must be finite and > 0")
            g_values = words.get("G", [])
            if len(g_values) != 1:
                report.errors.append(f"line {line_no}: exactly one explicit G00 or G01 is required per motion line")
                continue
            g = g_values[0]
            if g not in _SUPPORTED_MOTION:
                if g in ("2", "02", "3", "03") and self.allow_arcs:
                    report.errors.append(f"line {line_no}: arcs are not implemented by this validator yet")
                else:
                    report.errors.append(f"line {line_no}: unsupported or disabled G-code G{g}")
                continue
            axes = [axis for axis in ("X", "Y", "Z") if axis in words]
            if not axes:
                report.errors.append(f"line {line_no}: motion requires at least one XYZ coordinate")
                continue
            for axis in axes:
                value = float(words[axis][0])
                if not math.isfinite(value):
                    report.errors.append(f"line {line_no}: {axis} coordinate is not finite")
                    continue
                position[axis] = value
                limit = self.axis_limits.get(axis)
                if limit and not (limit.minimum <= value <= limit.maximum):
                    report.errors.append(f"line {line_no}: {axis}={value:g} outside configured range [{limit.minimum:g}, {limit.maximum:g}]")
            report.motion_lines += 1
        report.final_position = position
        if self.expected_unit is None:
            report.warnings.append("Units are not encoded by this restricted Estlcam dialect; verify the Estlcam program length-unit setting before simulation.")
        if set(self.axis_limits) != {"X", "Y", "Z"}:
            report.warnings.append("Full XYZ travel-envelope check is unavailable until all machine limits are measured.")
        if not report.errors:
            report.warnings.append("Static validation only: this is not Estlcam simulation, collision checking, machine verification, or authorization to run the program.")
        return report
