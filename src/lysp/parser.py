import string
from collections.abc import Callable
from dataclasses import dataclass, field

from .errors import LyspError

__all__ = [
    "AST",
    "Constant",
    "Id",
    "ParsingError",
    "Sexp",
    "Stream",
    "parse_from_str",
    "parse_from_stream",
]

_ID_FIRST = string.ascii_letters + "!#$%&*+,-./:;<=>?@_`~"
_ID_ALPHABET = _ID_FIRST + string.digits


class ParsingError(LyspError):
    """Raised when a parsing error occurs."""


class Stream:
    def __init__(self, data: str):
        self._data = list(data)
        self._pos = 0
        self._line = 0
        self._col = 0

    @property
    def line(self) -> int:
        return self._line

    @property
    def col(self) -> int:
        return self._col

    def peek(self, offset: int = 0) -> str | None:
        return (
            self._data[self._pos + offset]
            if offset >= 0 and self._pos + offset < len(self._data)
            else None
        )

    def next(self) -> str | None:
        c = self.peek()

        if c is None:
            return None
        self._pos += 1

        if c == "\n":
            self._line += 1
            self._col = 0
        else:
            self._col += 1
        return c

    def take_while(self, pred: Callable[[str], bool]) -> str:
        result = []
        while (c := self.peek()) is not None and pred(c):
            self.next()
            result.append(c)
        return "".join(result)


@dataclass
class AST:
    line: int | None = field(default=None, kw_only=True, compare=False)
    col: int | None = field(default=None, kw_only=True, compare=False)


@dataclass
class Sexp(AST):
    value: list[AST] = field(default_factory=list)


@dataclass
class Constant(AST):
    value: int | str | bool | None


@dataclass
class Id(AST):
    value: str


def is_number_start(current: str, next_: str | None) -> bool:
    return current in string.digits or (
        current in "+-" and next_ is not None and next_ in string.digits
    )


def parse_number(stream: Stream) -> Constant:
    line, col = stream.line, stream.col
    if (c := stream.peek()) is None or not is_number_start(c, stream.peek(1)):
        raise ParsingError(
            "number must start with a digit or a sign", line=stream.line, col=stream.col
        )
    result = ""
    # Handle sign if any
    if c in "+-":
        stream.next()
        result = c
    result += stream.take_while(lambda c: c in string.digits)
    return Constant(value=int(result), line=line, col=col)


def parse_string(stream: Stream) -> Constant:
    line, col = stream.line, stream.col
    if stream.peek() != '"':
        raise ParsingError(
            "string must start with '\"'", line=stream.line, col=stream.col
        )
    stream.next()  # discard first "
    result = stream.take_while(lambda c: c != '"')
    if stream.peek() != '"':
        raise ParsingError(
            "string must end with '\"'", line=stream.line, col=stream.col
        )
    stream.next()  # discard second "
    return Constant(value=result, line=line, col=col)


_KEYWORDS = {
    "null": None,
    "true": True,
    "false": False,
}


def parse_symbol(stream: Stream) -> Id | Constant:
    line, col = stream.line, stream.col
    if (c := stream.peek()) is None or c not in _ID_FIRST:
        c = "EOF" if c is None else c
        raise ParsingError(
            f"symbol cannot start with '{c}'", line=stream.line, col=stream.col
        )
    result = stream.take_while(lambda c: c in _ID_ALPHABET)
    if result in _KEYWORDS:
        return Constant(value=_KEYWORDS[result], line=line, col=col)
    return Id(value=result, line=line, col=col)


def parse_sexp(stream: Stream) -> Sexp:
    line, col = stream.line, stream.col
    if stream.peek() != "(":
        raise ParsingError("sexp must start with '('", line=stream.line, col=stream.col)
    stream.next()  # discard (
    sexp = []
    while True:
        skip_blank(stream)
        if stream.peek() is None:
            raise ParsingError(
                "sexp must end with ')'", line=stream.line, col=stream.col
            )
        if stream.peek() == ")":
            break
        sexp.append(parse_form(stream))
    stream.next()  # discard )
    return Sexp(value=sexp, line=line, col=col)


def skip_blank(stream: Stream) -> None:
    while (c := stream.peek()) is not None and c in string.whitespace:
        stream.next()


def parse_form(stream: Stream) -> AST:
    skip_blank(stream)

    c = stream.peek()
    if c is None:
        raise ParsingError("unexpected EOF", line=stream.line, col=stream.col)
    if c == "(":
        return parse_sexp(stream)
    if is_number_start(c, stream.peek(1)):
        return parse_number(stream)
    if c == '"':
        return parse_string(stream)
    if c in _ID_FIRST:
        return parse_symbol(stream)

    raise ParsingError(f"unexpected char '{c}'", line=stream.line, col=stream.col)


def parse_from_stream(stream: Stream) -> Sexp:
    line, col = stream.line, stream.col
    program = []
    while True:
        skip_blank(stream)
        if stream.peek() is None:
            break
        form = parse_form(stream)
        program.append(form)
    return Sexp(value=program, line=line, col=col)


def parse_from_str(src: str) -> Sexp:
    stream = Stream(src)
    return parse_from_stream(stream)
