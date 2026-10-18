"""The clean-room reference must be independent, and a docstring is not proof.

The whole value of a third implementation is that it shares no code with the
other two. If it imported production, or imported the independent checker, it
would be the second implementation wearing a hat and the three-way agreement
would mean nothing.

So independence is MEASURED, in a fresh interpreter, by inspecting
`sys.modules` after the import. A promise in a module docstring survives any
amount of drift; this does not.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEANROOM_DIR = os.path.join(ROOT, "research", "physical_validation",
                             "cleanroom")
CLEANROOM = os.path.join(CLEANROOM_DIR, "structural_reference.py")

#: Anything whose presence would compromise independence.
FORBIDDEN_PREFIXES = ("csia", "engineering", "independent_checker",
                      "numpy", "yaml", "scipy", "pandas")


def test_the_cleanroom_imports_nothing_that_would_compromise_it():
    """Run it in a fresh interpreter and look at what actually got loaded.

    Static analysis of the import statements would miss a lazy import inside
    a function; this catches both.
    """
    probe = (
        "import sys, json;"
        f"sys.path.insert(0, {CLEANROOM_DIR!r});"
        "import structural_reference as m;"
        # Exercise every public entry point, so a lazy import inside any of
        # them is triggered before we look.
        "sig={'a':{'f1'},'b':{'f2'},'c':set()};"
        "g={'f1':1.0,'f2':0.0};"
        "m.analyse(sig,g);"
        "m.equivalence_classes(sig,g);"
        "[m.classify(h,sig,g) for h in sig];"
        "print(json.dumps(sorted(sys.modules)))"
    )
    proc = subprocess.run([sys.executable, "-c", probe],
                          capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    loaded = json.loads(proc.stdout)

    offenders = sorted({
        m for m in loaded
        if any(m == p or m.startswith(p + ".") for p in FORBIDDEN_PREFIXES)})
    assert not offenders, (
        f"the clean-room reference loaded {offenders}. It exists to be a "
        f"THIRD implementation sharing no code with production or with the "
        f"independent checker; importing either makes the three-way "
        f"agreement meaningless.")


def test_the_cleanroom_has_no_repository_imports_in_its_source():
    """The static half. Catches an import that exists but was not reached."""
    with open(CLEANROOM, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    offenders = [n for n in names
                 if any(n == p or n.startswith(p + ".")
                        for p in FORBIDDEN_PREFIXES)]
    assert not offenders, f"forbidden imports in source: {offenders}"


def test_the_cleanroom_stays_small_enough_to_read():
    """A reference implementation nobody reads is not a check on anything.

    The number is a ceiling with room, not a target: the point is that a
    reviewer can hold the whole thing in their head, and that stops being
    true somewhere well before a thousand lines.
    """
    with open(CLEANROOM, encoding="utf-8") as fh:
        lines = fh.readlines()
    code = [l for l in lines
            if l.strip() and not l.strip().startswith("#")]
    assert len(code) < 200, (
        f"the clean-room reference has grown to {len(code)} code lines. It is "
        f"supposed to be small and boring enough to check by reading. If it "
        f"needs to be bigger, say why here rather than raising the number "
        f"silently.")


def test_the_definition_is_one_expression():
    """`distinguishing_terms` is the entire reference. Everything else is
    bookkeeping, and if that stops being true the file has grown a second
    idea that nobody reviewed."""
    sys.path.insert(0, CLEANROOM_DIR)
    import structural_reference as CR

    body = ast.parse(open(CLEANROOM, encoding="utf-8").read())
    fn = next(n for n in ast.walk(body)
              if isinstance(n, ast.FunctionDef)
              and n.name == "distinguishing_terms")
    statements = [s for s in fn.body if not isinstance(s, ast.Expr)]
    assert len(statements) == 1, (
        f"distinguishing_terms has {len(statements)} statements. The whole "
        f"reference is one set expression; more than that means a special "
        f"case crept in.")
    # And it really is the symmetric difference intersected with active.
    assert CR.distinguishing_terms({"a", "b"}, {"b", "c"}, {"a", "c"}) == \
        frozenset({"a", "c"})
    assert CR.distinguishing_terms({"a"}, {"a"}, {"a"}) == frozenset()
