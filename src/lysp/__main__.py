import argparse
import sys

from . import parser, transpiler


def parse_args() -> argparse.Namespace:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("input", type=argparse.FileType("r"))
    arg_parser.add_argument("--output", type=argparse.FileType("w"), default=sys.stdout)
    return arg_parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        src = args.input.read()
        program = parser.parse_from_str(src)
        ctx = transpiler.Context()
        module = transpiler.compile_module(program, ctx)
        output = transpiler.ast_to_str(module)
        args.output.write(output)
    except parser.ParsingError as e:
        print(f"Parsing error: {e}", file=sys.stderr)
        sys.exit(1)
    except transpiler.TranspilationError as e:
        print(f"Transpilation error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        args.input.close()
        if args.output is not sys.stdout:
            args.output.close()


if __name__ == "__main__":
    main()
