__all__ = ["LyspError"]


class LyspError(Exception):
    """Mother class of all Lysp's exceptions.

    Parameters
    ----------
    message : str
        Error message.

    line : int | None
        The line where the error occurred.

    col : int | None
        The column where the error occurred.
    """

    def __init__(
        self, message: str, *, line: int | None = None, col: int | None = None
    ):
        loc = (
            f" at line {line + 1}:{col + 1}"
            if line is not None and col is not None
            else ""
        )
        message = f"{message}{loc}"
        super().__init__(message)
        self.line = line
        self.col = col
