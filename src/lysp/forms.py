from dataclasses import dataclass, field

__all__ = [
    "AST",
    "Constant",
    "Id",
    "Sexp",
]


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
