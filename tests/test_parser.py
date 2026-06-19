import re

import pytest

from lysp.parser import (
    Constant,
    Id,
    ParsingError,
    Sexp,
    Stream,
    is_number_start,
    parse_form,
    parse_from_str,
    parse_from_stream,
    parse_id,
    parse_number,
    parse_sexp,
    parse_string,
    skip_blank,
)


class TestStream:
    def test_instantiate(self):
        Stream("hello")

    def test_peek_next(self):
        stream = Stream("hello")

        assert stream.peek() == "h"
        assert stream.peek(0) == "h"
        assert stream.peek(1) == "e"
        assert stream.peek(2) == "l"
        assert stream.peek(10) is None
        assert stream.peek(-2) is None

        assert stream.next() == "h"
        assert stream.peek() == "e"
        assert stream.next() == "e"
        assert stream.next() == "l"
        assert stream.next() == "l"
        assert stream.next() == "o"
        assert stream.next() is None

    def test_take_while(self):
        stream = Stream("aaabbb")
        assert stream.take_while(lambda c: c == "a") == "aaa"
        assert stream.peek() == "b"
        assert stream.take_while(lambda c: c == "a") == ""
        assert stream.take_while(lambda c: c == "b") == "bbb"
        assert stream.take_while(lambda _: True) == ""

    def test_line_col(self):
        stream = Stream("aaa\nbbb")

        assert stream.line == 0
        assert stream.col == 0
        stream.next()
        assert stream.line == 0
        assert stream.col == 1
        stream.next()
        assert stream.line == 0
        assert stream.col == 2
        stream.next()
        assert stream.line == 0
        assert stream.col == 3
        stream.next()
        assert stream.line == 1
        assert stream.col == 0
        stream.next()
        assert stream.line == 1
        assert stream.col == 1
        stream.next()
        assert stream.line == 1
        assert stream.col == 2
        stream.next()
        assert stream.line == 1
        assert stream.col == 3
        stream.next()
        assert stream.line == 1
        assert stream.col == 3


def test_is_number_start():
    assert not is_number_start("a", "1")
    assert not is_number_start("+", "a")
    assert not is_number_start("-", "a")
    assert is_number_start("1", "1")
    assert is_number_start("+", "1")
    assert is_number_start("-", "1")
    assert is_number_start("1", None)


def test_parse_number():
    def check_parse(data):
        result = parse_number(Stream(data))
        expected = Constant(int(data))
        assert result == expected

    check_parse("0")
    check_parse("+0")
    check_parse("-0")
    check_parse("123")
    check_parse("+123")
    check_parse("-123")

    with pytest.raises(
        ParsingError,
        match=re.escape("number must start with a digit or a sign at line 1:1"),
    ):
        check_parse("")
    with pytest.raises(
        ParsingError,
        match=re.escape("number must start with a digit or a sign at line 1:1"),
    ):
        check_parse("a")
    with pytest.raises(
        ParsingError,
        match=re.escape("number must start with a digit or a sign at line 1:1"),
    ):
        check_parse("+")
    with pytest.raises(
        ParsingError,
        match=re.escape("number must start with a digit or a sign at line 1:1"),
    ):
        check_parse("-")


def test_parse_string():
    def check_parse(data):
        result = parse_string(Stream(data))
        expected = Constant(data.replace('"', ""))  # will break after implementing \"
        assert result == expected

    check_parse('""')
    check_parse('"a"')
    check_parse('"hello"')
    check_parse('"hello world!"')

    with pytest.raises(
        ParsingError, match=re.escape("string must start with '\"' at line 1:1")
    ):
        check_parse("")
    with pytest.raises(
        ParsingError, match=re.escape("string must end with '\"' at line 1:2")
    ):
        check_parse('"')
    with pytest.raises(
        ParsingError, match=re.escape("string must end with '\"' at line 1:7")
    ):
        check_parse('"hello')


def test_parse_id():
    def check_parse(data):
        result = parse_id(Stream(data))
        expected = Id(data)
        assert result == expected

    check_parse("+")
    check_parse("id")
    check_parse("hello-world")
    check_parse("empty?")

    with pytest.raises(
        ParsingError, match=re.escape("id cannot start with 'EOF' at line 1:1")
    ):
        check_parse("")
    with pytest.raises(
        ParsingError, match=re.escape("id cannot start with '\\' at line 1:1")
    ):
        check_parse("\\")


def test_parse_sexp():
    assert parse_sexp(Stream("()")) == Sexp([])
    assert parse_sexp(Stream("(123)")) == Sexp([Constant(123)])
    assert parse_sexp(Stream('(id 123 "hello")')) == Sexp(
        [Id("id"), Constant(123), Constant("hello")]
    )
    assert parse_sexp(Stream('((id 123) "hello")')) == Sexp(
        [Sexp([Id("id"), Constant(123)]), Constant("hello")]
    )
    assert parse_sexp(Stream('((id (123)) ("hello") ())')) == Sexp(
        [Sexp([Id("id"), Sexp([Constant(123)])]), Sexp([Constant("hello")]), Sexp([])]
    )

    with pytest.raises(ParsingError, match=re.escape("sexp must start with '('")):
        parse_sexp(Stream(""))
    with pytest.raises(ParsingError, match=re.escape("sexp must end with ')'")):
        parse_sexp(Stream('(define 123 "str"'))
    with pytest.raises(ParsingError, match=re.escape("sexp must start with '('")):
        parse_sexp(Stream(")"))


def test_skip_blank():
    stream = Stream("a")
    skip_blank(stream)
    assert stream.peek() == "a"

    stream = Stream("    \t\n   a")
    skip_blank(stream)
    assert stream.peek() == "a"


def test_parse_form():
    assert parse_form(Stream("   123")) == Constant(123)
    assert parse_form(Stream('   "hello"')) == Constant("hello")
    assert parse_form(Stream("   id")) == Id("id")
    assert parse_form(Stream("   (id)")) == Sexp([Id("id")])

    with pytest.raises(ParsingError, match="unexpected EOF"):
        parse_form(Stream(""))
    with pytest.raises(ParsingError, match="unexpected EOF"):
        parse_form(Stream("   "))
    with pytest.raises(
        ParsingError, match=re.escape("unexpected char '\\' at line 1:1")
    ):
        parse_form(Stream("\\"))


def test_parse_from_stream():
    stream = Stream("""
        (a 1)
        (b 2)
    """)
    result = parse_from_stream(stream)
    assert result == Sexp(
        [
            Sexp([Id("a"), Constant(1)]),
            Sexp([Id("b"), Constant(2)]),
        ]
    )

    assert parse_from_stream(Stream("")) == Sexp([])


def test_parse_from_str():
    src = """
        (a 1)
        (b 2)
    """
    result = parse_from_str(src)
    assert result == Sexp(
        [
            Sexp([Id("a"), Constant(1)]),
            Sexp([Id("b"), Constant(2)]),
        ]
    )

    assert parse_from_str("") == Sexp([])


def test_position():
    forms = parse_from_str("123\n  abc").value
    assert (forms[0].line, forms[0].col) == (0, 0)
    assert (forms[1].line, forms[1].col) == (1, 2)
