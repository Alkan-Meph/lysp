# Lysp 🐍

Lysp is a tiny Lisp programming language that transpiles to Python.

⚠️ It's a work in progress.

## Examples

### Factorial

```lisp
(define fact (lambda (n)
    (if (<= n 1)
        1
        (* n (fact (- n 1))))))

(print (fact 5))
(print (fact 10))
```

compiles to:

```python
def fact(n):
    return 1 if n <= 1 else n * fact(n - 1)
fact
print(fact(5))
print(fact(10))
```

### Iter

```lisp
(define _iter (lambda (fn l i)
    (if (< i (len l))
        (do
            (fn (nth l i))
            (_iter fn l (+ i 1)))
        null)))

(define iter (lambda (fn l) (_iter fn l 0)))

(iter print (list "hello" "world"))
```

compiles to:

```python
def _iter(fn, l, i):
    if i < len(l):
        fn(l[i])
        _lysp_0_ = _iter(fn, l, i + 1)
    else:
        _lysp_0_ = None
    return _lysp_0_
_iter

def iter(fn, l):
    return _iter(fn, l, 0)
iter
iter(print, ['hello', 'world'])
```

## Install

Requirements:

- Python >= 3.14
- uv

```bash
git clone git@github.com:Alkan-Meph/lysp.git
cd lysp
uv sync
```

## Use it

Transpile and display the result on `stdout`:

```bash
uv run lysp examples/list.lysp
```

Transpile and execute:

```bash
uv run lysp examples/list.lysp | python3
```

Transpile into a file then execute:

```bash
uv run lysp examples/list.lysp --output /tmp/list.py
python3 /tmp/list.py
```
