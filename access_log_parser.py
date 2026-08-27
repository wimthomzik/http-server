import json
from dataclasses import dataclass

REQUIRED = ('method', 'path', 'status', 'duration')

NO_VALUE = "-"

class ParseError(Exception):
    """A line that claims to be an access line but is not a valid one"""

@dataclass(frozen=True)
class AccessRecord:
    method: str
    path: str
    status: int
    duration: float
    raw_line: str
    lineno: int
    
def _parse_json(line):
    try:
        value = json.loads(line)
    except ValueError:
        return None
    value if isinstance(value, dict) else None
    
def _text(field, value, raw, lineno):
    if not value or not isinstance(value, str):
        raise ParseError(f"line {lineno}: {field} is not a non-empty string : {raw!r}")
    return value

def _status(field, value, raw, lineno):
    if value == NO_VALUE:
        return value
    if not isinstance(value, int) or isinstance(value, bool):
        raise ParseError(f"line {lineno}: {field} is neither an int nor {NO_VALUE} : {raw!r}")
    if not 100 <= value <= 599:
        raise ParseError(f"line {lineno}: {field} {value} is not a status code : {raw!r}")
    return value

def _duration(field, value, raw, lineno):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ParseError(f"line {lineno}: {field} is not a number : {raw!r}")
    if value < 0:
        raise ParseError(f"line {lineno}: {field} is negative {value} : {raw!r}")
    return float(value)
    
def _record(obj, raw, lineno):
    absent = [a for a in REQUIRED if a not in obj]
    if absent:
        raise ParseError(f"line {lineno}: missing {', '.join(absent)}: {raw!r}")
    
    return AccessRecord(
        method=_text('method', obj['method'], raw, lineno),
        path=_text('path', obj['path'], raw, lineno),
        status=_status('status', obj['status'], raw, lineno),
        duration=_duration('duration', obj['duration'], raw, lineno),
        raw_line=raw,
        lineno=lineno
    )

def parse_access_log(text: str) -> list[AccessRecord]:
   return [
       _record(obj, line, lineno)
       for lineno, line in enumerate(text.splitlines(), start=1)
       if (obj := _parse_json(line)) is not None
   ]
