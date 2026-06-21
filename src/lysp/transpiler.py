import ast
import itertools
import keyword
from collections.abc import Callable

from .errors import LyspError
from .forms import AST, Constant, Id, Sexp

__all__ = [
    "Context",
    "InvalidFormError",
    "TranspilationError",
    "ast_to_str",
    "compile_form",
    "compile_module",
]

CompileResult = tuple[list[ast.stmt], ast.expr]
CompileFn = Callable[[Sexp, "Context"], CompileResult]
Env = dict[str, CompileFn]
BuildFn = Callable[[ast.expr, ast.expr], ast.expr]


class TranspilationError(LyspError):
    """Mother class of all transpilation's error."""


class InvalidFormError(TranspilationError):
    """Raised when an invalid form is parsed."""

    def __init__(self, form: AST, *, line: int | None = None, col: int | None = None):
        super().__init__(f"invalid form '{form}'", line=line, col=col)
        self.form = form


class Context:
    def __init__(self, env: Env | None = None):
        self._env = env if env is not None else make_env()
        self._counter = itertools.count()

    @property
    def env(self) -> Env:
        return self._env

    def make_name(self) -> str:
        # TODO: handle name conflicts (user can define symbols with same name)
        name = next(self._counter)
        return f"_lysp_{name}_"

    def reset_name(self) -> None:
        self._counter = itertools.count()


def compile_constant(constant: Constant) -> ast.Constant:
    return ast.Constant(value=constant.value)


_SYMBOL_NAMES = {
    "!": "bang",
    "#": "hash",
    "$": "dollar",
    "%": "percent",
    "&": "amp",
    "*": "star",
    "+": "plus",
    ",": "comma",
    "-": "dash",
    ".": "dot",
    "/": "slash",
    ":": "colon",
    ";": "semi",
    "<": "lt",
    "=": "eq",
    ">": "gt",
    "?": "question",
    "@": "at",
    "_": "underscore",
    "`": "backtick",
    "~": "tilde",
}


def mangle(name: str) -> str:
    if name.isidentifier() and not keyword.iskeyword(name):
        return name
    result = "".join(f"_{_SYMBOL_NAMES[c]}_" if c in _SYMBOL_NAMES else c for c in name)
    return f"_lysp_{result}"


def compile_id(id_: Id) -> ast.Name:
    return ast.Name(id=mangle(id_.value))


def compile_lambda(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("lambda"), Sexp(params), body]):
            args = []
            for param in params:
                if not isinstance(param, Id):
                    raise TranspilationError(
                        "lambda params must be ids", line=param.line, col=param.col
                    )
                args.append(ast.arg(arg=mangle(param.value)))
            stmts, value = compile_form(body, ctx)
            stmts.append(ast.Return(value=value))
            tmp = ctx.make_name()
            fn = ast.FunctionDef(
                name=tmp,
                args=ast.arguments(args=args),
                body=stmts,
            )
            return [fn], ast.Name(id=tmp)
        case _:
            raise TranspilationError(
                "lambda expects (lambda <params> <body>)", line=sexp.line, col=sexp.col
            )


def compile_define(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("define"), Id(name), body]):
            stmts, value = compile_form(body, ctx)
            name = mangle(name)
            match stmts:
                case [ast.FunctionDef() as fn]:
                    fn.name = name
                case _:
                    target = ast.Name(id=name, ctx=ast.Store())
                    assign = ast.Assign(targets=[target], value=value)
                    stmts.append(assign)
            return stmts, ast.Name(id=name, ctx=ast.Load())
        case _:
            raise TranspilationError(
                "define expects (define <name> <body>)", line=sexp.line, col=sexp.col
            )


def compile_do(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("do"), *forms]) if len(forms) > 0:
            stmts = []
            for form in forms[:-1]:
                form_stmts, form_value = compile_form(form, ctx)
                stmts.extend(form_stmts)
                stmts.append(ast.Expr(form_value))
            form_stmts, form_value = compile_form(forms[-1], ctx)
            stmts.extend(form_stmts)
            return stmts, form_value
        case _:
            raise TranspilationError(
                "do expects (do ...)", line=sexp.line, col=sexp.col
            )


def compile_if(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("if"), test, then, else_]):
            test_stmts, test_value = compile_form(test, ctx)
            then_stmts, then_value = compile_form(then, ctx)
            else_stmts, else_value = compile_form(else_, ctx)

            # IfExp case
            if len(test_stmts) == len(then_stmts) == len(else_stmts) == 0:
                if_exp = ast.IfExp(test=test_value, body=then_value, orelse=else_value)
                return [], if_exp

            # If case
            tmp = ctx.make_name()
            target = ast.Name(id=tmp, ctx=ast.Store())
            then_stmts.append(ast.Assign(targets=[target], value=then_value))
            else_stmts.append(ast.Assign(targets=[target], value=else_value))
            if_ = ast.If(test=test_value, body=then_stmts, orelse=else_stmts)
            test_stmts.append(if_)
            return test_stmts, ast.Name(id=tmp, ctx=ast.Load())

        case _:
            raise TranspilationError(
                "if expects (if <test> <then> <else>)", line=sexp.line, col=sexp.col
            )


def compile_list(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("list"), *items]):
            stmts = []
            elts = []
            for item in items:
                item_stmts, item_value = compile_form(item, ctx)
                stmts.extend(item_stmts)
                elts.append(item_value)
            return stmts, ast.List(elts=elts, ctx=ast.Load())
        case _:  # pragma: no cover
            raise TranspilationError(
                "list expects (list ...)", line=sexp.line, col=sexp.col
            )


def compile_append(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("append"), *items]) if len(items) >= 1:
            stmts = []
            elts = []
            for item in items:
                item_stmts, item_value = compile_form(item, ctx)
                stmts.extend(item_stmts)
                elts.append(item_value)
            # Fold left the items to produce ((x + y) + z) + ...
            result = elts[0]
            for elt in elts[1:]:
                result = ast.BinOp(op=ast.Add(), left=result, right=elt)
            return stmts, result
        case _:
            raise TranspilationError(
                "append expects (append <list> ...)", line=sexp.line, col=sexp.col
            )


def compile_nth(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("nth"), list_, index]):
            list_stmts, list_value = compile_form(list_, ctx)
            index_stmts, index_value = compile_form(index, ctx)
            list_stmts.extend(index_stmts)
            subscript = ast.Subscript(
                value=list_value, slice=index_value, ctx=ast.Load()
            )
            return list_stmts, subscript
        case _:
            raise TranspilationError(
                "nth expects (nth <list> <index>)", line=sexp.line, col=sexp.col
            )


def compile_hd(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("hd"), list_]):
            stmts, value = compile_form(list_, ctx)
            subscript = ast.Subscript(
                value=value, slice=ast.Constant(value=0), ctx=ast.Load()
            )
            return stmts, subscript
        case _:
            raise TranspilationError(
                "hd expects (hd <list>)", line=sexp.line, col=sexp.col
            )


def compile_tl(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("tl"), list_]):
            stmts, value = compile_form(list_, ctx)
            slice_ = ast.Slice(lower=ast.Constant(value=1))
            subscript = ast.Subscript(value=value, slice=slice_, ctx=ast.Load())
            return stmts, subscript
        case _:
            raise TranspilationError(
                "tl expects (tl <list>)", line=sexp.line, col=sexp.col
            )


def compile_call(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([callee, *params]):
            stmts, value = compile_form(callee, ctx)
            args = []
            for param in params:
                param_stmts, param_value = compile_form(param, ctx)
                stmts.extend(param_stmts)
                args.append(param_value)
            call = ast.Call(func=value, args=args)
            return stmts, call
        case _:
            raise TranspilationError(
                "cannot compile empty form", line=sexp.line, col=sexp.col
            )


def compile_apply(sexp: Sexp, ctx: Context) -> CompileResult:
    match sexp:
        case Sexp([Id("apply"), callee, *params]) if len(params) >= 1:
            stmts, value = compile_form(callee, ctx)
            args = []
            for param in params:
                param_stmts, param_value = compile_form(param, ctx)
                stmts.extend(param_stmts)
                args.append(param_value)
            args[-1] = ast.Starred(value=args[-1], ctx=ast.Load())
            call = ast.Call(func=value, args=args)
            return stmts, call
        case _:
            raise TranspilationError(
                "apply expects (apply fn ...)", line=sexp.line, col=sexp.col
            )


def compile_op(build: BuildFn) -> CompileFn:
    def _compile(sexp: Sexp, ctx: Context) -> CompileResult:
        match sexp:
            case Sexp([Id(), left, right]):
                left_stmts, left_value = compile_form(left, ctx)
                right_stmts, right_value = compile_form(right, ctx)
                left_stmts.extend(right_stmts)
                return left_stmts, build(left_value, right_value)
            case _:
                raise TranspilationError(
                    "op expects (<op> <expr> <expr>)", line=sexp.line, col=sexp.col
                )

    return _compile


def compile_binop(op: ast.operator) -> CompileFn:
    return compile_op(lambda left, right: ast.BinOp(op=op, left=left, right=right))


def compile_boolop(op: ast.boolop) -> CompileFn:
    return compile_op(lambda left, right: ast.BoolOp(op=op, values=[left, right]))


def compile_cmpop(op: ast.cmpop) -> CompileFn:
    return compile_op(
        lambda left, right: ast.Compare(ops=[op], left=left, comparators=[right])
    )


def make_env() -> Env:
    env: Env = {
        "lambda": compile_lambda,
        "define": compile_define,
        "if": compile_if,
        "do": compile_do,
        "list": compile_list,
        "append": compile_append,
        "nth": compile_nth,
        "hd": compile_hd,
        "tl": compile_tl,
        "apply": compile_apply,
        "+": compile_binop(ast.Add()),
        "-": compile_binop(ast.Sub()),
        "*": compile_binop(ast.Mult()),
        "/": compile_binop(ast.Div()),
        "and": compile_boolop(ast.And()),
        "or": compile_boolop(ast.Or()),
        "=": compile_cmpop(ast.Eq()),
        "!=": compile_cmpop(ast.NotEq()),
        "<": compile_cmpop(ast.Lt()),
        "<=": compile_cmpop(ast.LtE()),
        ">": compile_cmpop(ast.Gt()),
        ">=": compile_cmpop(ast.GtE()),
    }
    return env


def compile_form(form: AST, ctx: Context) -> CompileResult:
    match form:
        case Constant():
            return [], compile_constant(form)
        case Id():
            return [], compile_id(form)
        case Sexp([Id(head), *_]) if head in ctx.env:
            return ctx.env[head](form, ctx)
        case Sexp():
            return compile_call(form, ctx)
    raise InvalidFormError(form, line=form.line, col=form.col)


def compile_module(program: Sexp, ctx: Context) -> ast.Module:
    # TODO: visitors to simplify the Python ast
    body: list[ast.stmt] = []
    for form in program.value:
        stmts, value = compile_form(form, ctx)
        body.extend(stmts)
        body.append(ast.Expr(value))
    module = ast.Module(body=body)
    ast.fix_missing_locations(module)
    return module


def ast_to_str(tree: ast.AST) -> str:
    return ast.unparse(tree) + "\n"
