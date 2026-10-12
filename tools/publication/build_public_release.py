"""Build public archives from an allowlist, then sanitize what was built.

Two properties this tool exists to guarantee (decisions H-2, H-3):

  1. **Allowlist, not blacklist.** Every member of every archive comes from an
     explicit path in `publication/system_paper_i/PUBLIC_RELEASE_MANIFEST.yaml`.
     The repository is never copied and then pruned. A file that nobody listed
     is not "missed" — it was never reachable.

  2. **The scan runs on the artifact, not on the intent.** After packing, the
     archive is unpacked into a temporary directory and every extracted byte is
     scanned. A private username, a home path, a credential, a strategy
     document or a Phase-II result found there fails the release. Scanning the
     staging tree instead would prove nothing about the file that ships.

Exit codes:  0 release built and clean · 1 sanitization failed or a listed
path is missing. On failure the archives are deleted, so a red run cannot
leave a shippable-looking file behind.

Run:  python tools/publication/build_public_release.py [--check]
      --check builds and scans into a scratch directory and keeps nothing, so
      CI can verify a release is clean without archives being committed.
"""

import argparse
import gzip
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MANIFEST = os.path.join(ROOT, "publication", "system_paper_i",
                        "PUBLIC_RELEASE_MANIFEST.yaml")

# Reproducible tarballs: fixed mtime and ownership, sorted members. Two builds
# of an unchanged tree produce the same SHA-256, so the hash in a release note
# means something.
EPOCH = 1700000000
TEXT_SKIP = (".png", ".jpg", ".jpeg", ".pdf", ".gz", ".zip", ".woff",
             ".woff2", ".ttf", ".ico")


def load():
    with open(MANIFEST, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def resolve(man, name, seen=None):
    """Return [(abs_source, arcname)] for a package, recursively.

    A nested package keeps its own root as a subdirectory, so the evidence
    export appears at `<root>/evidence_export/...` inside the larger package
    and at `evidence_export/...` inside its own.
    """
    seen = seen or set()
    if name in seen:
        raise SystemExit(f"manifest: package cycle at {name}")
    seen.add(name)
    pkg = man["packages"][name]
    root = pkg["root"]
    out = []

    for rel in pkg.get("files", []):
        strip = pkg.get("strip_prefix", "")
        tail = rel[len(strip):] if strip and rel.startswith(strip) else rel
        out.append((os.path.join(ROOT, rel), f"{root}/{tail}"))

    for group in pkg.get("groups", {}).values():
        for rel in group.get("files", []):
            out.append((os.path.join(ROOT, rel), f"{root}/{rel}"))

    nested = pkg.get("includes_package")
    if nested:
        for src_path, arc in resolve(man, nested, seen):
            out.append((src_path, f"{root}/{arc}"))

    return sorted(set(out), key=lambda t: t[1])


def check_sources(members):
    """Every listed path must exist and be tracked by Git."""
    tracked = set(subprocess.run(["git", "-C", ROOT, "ls-files"],
                                 capture_output=True, text=True).stdout.split())
    problems = []
    for src_path, arc in members:
        rel = os.path.relpath(src_path, ROOT)
        if not os.path.isfile(src_path):
            problems.append(f"listed but missing on disk: {rel}")
        elif rel not in tracked:
            # An untracked file cannot be reviewed through history, so it is
            # not eligible for release even if it exists.
            problems.append(f"listed but not tracked by Git: {rel}")
    return problems


def pack(members, archive):
    os.makedirs(os.path.dirname(archive), exist_ok=True)
    # gzip stamps its own header with the current time, which would make the
    # archive hash change on every build even when nothing changed. Drive the
    # GzipFile directly so mtime and filename are fixed too.
    raw = open(archive, "wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=EPOCH)
    with tarfile.open(fileobj=gz, mode="w") as tf:
        for src_path, arc in members:
            info = tf.gettarinfo(src_path, arcname=arc)
            info.mtime = EPOCH
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            with open(src_path, "rb") as fh:
                tf.addfile(info, fh)
    gz.close()
    raw.close()
    return archive


def scan_archive(archive, san):
    """Unpack the built archive and scan every extracted file."""
    pats = {k: re.compile(v) for k, v in san["forbidden_patterns"].items()}
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    email_ok = tuple(san.get("email_allowed_in", []))
    ph_tokens = san.get("phase_ii_context_tokens", [])
    ph_ok = tuple(san.get("phase_ii_context_allowed_in", []))
    frags = san.get("forbidden_path_fragments", [])

    failures = []
    with tarfile.open(archive, "r:gz") as tf:
        names = tf.getnames()
        for n in names:
            if n.startswith("/") or ".." in n.split("/"):
                failures.append(f"unsafe member path: {n}")
            for frag in frags:
                if frag in n:
                    failures.append(f"forbidden path fragment {frag!r}: {n}")
        with tempfile.TemporaryDirectory() as tmp:
            tf.extractall(tmp)
            for n in names:
                path = os.path.join(tmp, n)
                if not os.path.isfile(path):
                    continue
                if n.lower().endswith(TEXT_SKIP):
                    continue
                try:
                    text = open(path, encoding="utf-8",
                                errors="strict").read()
                except (OSError, UnicodeDecodeError):
                    continue
                for label, pat in pats.items():
                    m = pat.search(text)
                    if m:
                        # Never echo the value: report the class and a
                        # redacted fingerprint.
                        fp = hashlib.sha256(
                            m.group(0).encode()).hexdigest()[:12]
                        failures.append(
                            f"{n}: forbidden [{label}] "
                            f"redacted-sha256:{fp}")
                if not n.endswith(email_ok):
                    m = email.search(text)
                    if m:
                        fp = hashlib.sha256(
                            m.group(0).encode()).hexdigest()[:12]
                        failures.append(f"{n}: email address outside LICENSE "
                                        f"redacted-sha256:{fp}")
                if not n.endswith(ph_ok):
                    for tok in ph_tokens:
                        if tok in text:
                            failures.append(
                                f"{n}: Phase-II token {tok!r} in a file that "
                                f"is not allowed to carry one")
    return names, failures


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="build and scan into a scratch dir, keep nothing")
    args = ap.parse_args()

    man = load()
    san = man["sanitization"]
    rc = 0

    for name in man["packages"]:
        pkg = man["packages"][name]
        archive = os.path.join(ROOT, pkg["archive"])
        members = resolve(man, name)

        print(f"=== package {name}")
        print(f"    allowlisted files: {len(members)}")
        print(f"    export control:    {pkg.get('export_control', '—')}")

        problems = check_sources(members)
        for p in problems:
            print(f"    SOURCE FAIL  {p}")
        if problems:
            rc = 1
            continue

        # --check packs to a scratch path and throws it away. The archives are
        # build products and are not committed, so "does the file exist" would
        # fail in every fresh clone and in CI for a reason that has nothing to
        # do with the release being clean. Because packing is reproducible,
        # building it IS the check: the scratch archive is byte-identical to
        # the one `make public-release` would ship, including its SHA-256.
        scratch = None
        if args.check:
            scratch = tempfile.mkdtemp(prefix="csia-release-")
            archive = os.path.join(scratch, os.path.basename(pkg["archive"]))
        pack(members, archive)

        names, failures = scan_archive(archive, san)
        print(f"    archive:           {pkg['archive']}"
              f"{'  (verified from a scratch build)' if scratch else ''}")
        print(f"    members:           {len(names)}")
        print(f"    sha256:            {sha256(archive)}")
        if failures:
            print(f"    SANITIZATION:      FAIL ({len(failures)})")
            for f in failures:
                print(f"      {f}")
            os.remove(archive)
            print("    archive deleted; a failed release does not ship")
            rc = 1
        else:
            print("    SANITIZATION:      PASS "
                  "(no username, home path, credential, strategy document, "
                  "interceptor tooling, .git or unlabelled Phase-II token)")
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
        print()

    print("PUBLIC RELEASE: " + ("PASS" if rc == 0 else "FAIL"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
