import re

import pytest

from lysp.parser import AST, parse_from_str
from lysp.transpiler import (
    Context,
    InvalidFormError,
    TranspilationError,
    ast_to_str,
    compile_form,
    compile_module,
)

_VALID_TESTS = {
    "(define x 1)": "x = 1\nx",
    '(define s "hello")': "s = 'hello'\ns",
    "(print (+ x 1))": "print(x + 1)",
    "(print (if x 1 2))": "print(1 if x else 2)",
    "(if x (define x 1) (define x 2))": """if x:
    x = 1
    _lysp_0_ = x
else:
    x = 2
    _lysp_0_ = x
_lysp_0_""",
    "(define f (lambda (x y) (+ x y)))": """def f(x, y):
    return x + y
f""",
    "(list)": "[]",
    "(list 1 2 3)": "[1, 2, 3]",
    '(list 1 x "hello")': "[1, x, 'hello']",
    "(list (list 1) (list 2 3) (list (list)))": "[[1], [2, 3], [[]]]",
    "(nth (list 1 2 3) 1)": "[1, 2, 3][1]",
    "(nth (list 1 2 3) (+ 4 5))": "[1, 2, 3][4 + 5]",
    "(do (print 1) (print 2))": "print(1)\nprint(2)",
    "(print (do 1 2))": "1\nprint(2)",
    "(do 1)": "1",
}

_INVALID_TESTS = {
    "(lambda (1) 1)": "lambda params must be ids",
    "(lambda (x) 1 2)": "lambda expects (lambda <params> <body>) at line 1:1",
    "(define 1 2)": "define expects (define <name> <body>) at line 1:1",
    "(if 1 2 3 4)": "if expects (if <test> <then> <else>) at line 1:1",
    "()": "cannot compile empty form at line 1:1",
    "(+)": "op expects (<op> <expr> <expr>) at line 1:1",
}


def test_context():
    ctx = Context()
    assert len({ctx.make_name() for _ in range(1000)}) == 1000
    ctx.reset_name()
    assert ctx.make_name() == "_lysp_0_"


def test_compile_module():
    def _compile(src):
        program = parse_from_str(src)
        ctx = Context()
        return compile_module(program, ctx)

    for to_check, expected in _VALID_TESTS.items():
        result = _compile(to_check)
        assert ast_to_str(result) == expected
        compile(
            result, "<test>", "exec"
        )  # check for internal inconsistencies like bad line or col

    for test, expected_message in _INVALID_TESTS.items():
        with pytest.raises(TranspilationError, match=re.escape(expected_message)):
            _compile(test)


def test_compile_form_invalid():
    with pytest.raises(InvalidFormError):
        compile_form(AST(), Context())
