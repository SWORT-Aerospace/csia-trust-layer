"""Publication guard: credential and local-path scan over tracked files.

Two severities, and only one of them fails the build.

  BLOCKING  a credential-shaped string: API keys, tokens, private key blocks,
            bearer headers. Any hit fails.
  REVIEW    a local filesystem path, a private address or an email in a
            tracked file. These are hygiene items, not leaks, and some are
            deliberate (a LICENSE carries an author's email on purpose). They
            are listed for a human, with an allowlist for the ones already
            reviewed and accepted.

Values are never printed in full: a blocking hit prints the file, the line and
a redacted fingerprint, never the secret.

Run:  python tools/publication/secrets_scan.py [--all-review]
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

BLOCKING = {
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "github_token": r"gh[pousr]_[A-Za-z0-9]{36,}",
    "openai_key": r"\bsk-[A-Za-z0-9]{32,}",
    "slack_token": r"xox[baprs]-[A-Za-z0-9-]{10,}",
    "google_api_key": r"AIza[0-9A-Za-z\-_]{35}",
    "private_key_block": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?"
                         r"PRIVATE KEY-----",
    "bearer_header": r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._\-]{20,}",
    "secret_assignment": r"(?i)\b(?:api[_-]?key|secret[_-]?key|auth[_-]?token"
                         r"|access[_-]?token|passwd|password)\s*[:=]\s*"
                         r"['\"][^'\"\s]{12,}['\"]",
}

REVIEW = {
    "mac_home_path": r"/Users/[A-Za-z][A-Za-z0-9_-]*",
    "linux_home_path": r"/home/[a-z][a-z0-9_-]*",
    "private_ipv4": r"\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+"
                    r"|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b",
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
}

# Reviewed and accepted. Each entry states WHY, so a later reader does not
# have to re-litigate it. Adding to this list is a decision, not a fix.
REVIEW_ALLOW = {
    ("email", "LICENSE"):
        "the copyright holder's own contact address, placed deliberately",
    # Documents whose PURPOSE is to report the finding. The string is the
    # subject of the sentence, not a leak. Allowlisting the reporter rather
    # than the source would be wrong, so the source rows stay flagged.
    #
    # The two `mac_home_path` entries that used to sit here are gone: decision
    # H-2 fixed the source instead of allowlisting the reporter, so no tracked
    # file contains an absolute macOS home path any more and there is nothing
    # left to allow.
    ("linux_home_path", "HARNESS_RELEASE_AUDIT.md"):
        "the audit quotes the container-local paths it reviewed",
    ("linux_home_path", "tools/publication/secrets_scan.py"):
        "this scanner's own allowlist keys contain the paths it allowlists",
    ("linux_home_path", "artifacts/ci/75881b9_failed_run.log"):
        "/home/runner/... is GitHub Actions' own workspace path inside a "
        "retained CI failure log; not a local machine and not sensitive",
    ("linux_home_path", "research/phase2/results/modern_replication.json"):
        "container-local ArduPilot checkout path recorded as provenance for "
        "a Phase-II artifact",
    ("linux_home_path", "research/phase2/modern_replication.py"):
        "CSIA_AP_ROOT default for the Phase-II SITL rig; overridable by env",
    ("linux_home_path", "research/phase2/modern_rig.py"):
        "CSIA_AP_ROOT default for the Phase-II SITL rig; overridable by env",
    ("linux_home_path", "tools/simulation/qualify_platform.py"):
        "CSIA_AP_ROOT / CSIA_PX4_ROOT defaults for the v1.1 qualification "
        "harness; both overridable by env, and neither is a personal path",
    ("linux_home_path", "Makefile"):
        "AP_ROOT / PX4_ROOT defaults for the qualification targets; "
        "overridable on the make command line",
    ("linux_home_path", "research/v1_1/results/qualification_ardupilot.json"):
        "container-local simulator path recorded as run provenance",
    ("linux_home_path", "research/v1_1/results/qualification_px4.json"):
        "container-local simulator path recorded as run provenance",
    ("linux_home_path", "research/phase2/results/e1_modern.json"):
        "container-local binary path recorded as Phase-II run provenance",
    ("linux_home_path",
     "research/phase2/results/e1_modern_run1_defective_instrument.json"):
        "container-local binary path recorded as Phase-II run provenance; "
        "this artifact is a preserved defective run and must not be edited",
    ("linux_home_path", "research/phase2/results/r10_modern.json"):
        "container-local binary path recorded as Phase-II run provenance",
    ("linux_home_path", "campaigns/results/shared_power_baseline_v1.json"):
        "container-local output path recorded as provenance",
    ("linux_home_path",
     "campaigns/results/shared_power_baseline_v1_manifest.json"):
        "container-local output path recorded as provenance",
    ("linux_home_path",
     "datasets/reports/csia_v1_cross_dataset_baseline_v1.json"):
        "container-local output path recorded as provenance",
}

BINARY_EXT = (".png", ".jpg", ".jpeg", ".pdf", ".gz", ".zip", ".so", ".o",
              ".whl", ".ico", ".woff", ".woff2", ".ttf")


def fingerprint(s):
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-review", action="store_true",
                    help="list allowlisted review hits too")
    args = ap.parse_args()

    files = subprocess.run(["git", "-C", ROOT, "ls-files"],
                           capture_output=True, text=True).stdout.split()
    blocking, review, allowed = [], [], []
    for rel in files:
        if rel.endswith(BINARY_EXT):
            continue
        path = os.path.join(ROOT, rel)
        try:
            text = open(path, encoding="utf-8", errors="strict").read()
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for name, pat in BLOCKING.items():
                m = re.search(pat, line)
                if m:
                    blocking.append((name, rel, n, fingerprint(m.group(0))))
            for name, pat in REVIEW.items():
                m = re.search(pat, line)
                if not m:
                    continue
                if (name, rel) in REVIEW_ALLOW:
                    allowed.append((name, rel))
                else:
                    review.append((name, rel, n, m.group(0)[:70]))

    print(f"=== scanned {len(files)} tracked files")
    print(f"  {'PASS' if not blocking else 'FAIL'}  credentials            "
          f"{len(blocking)} blocking hits")
    for name, rel, n, fp in blocking:
        print(f"        {rel}:{n}  [{name}]  redacted-sha256:{fp}")

    seen = {}
    for name, rel, n, snip in review:
        seen.setdefault((name, rel), []).append((n, snip))
    print(f"  ----  review items           {len(seen)} file/pattern pairs "
          f"not yet allowlisted")
    for (name, rel), hits in sorted(seen.items()):
        print(f"        {rel}  [{name}] x{len(hits)}  e.g. line "
              f"{hits[0][0]}: {hits[0][1]}")

    if args.all_review:
        print(f"  ----  allowlisted            "
              f"{len(set(allowed))} file/pattern pairs")
        for name, rel in sorted(set(allowed)):
            print(f"        {rel}  [{name}]  -- "
                  f"{REVIEW_ALLOW[(name, rel)]}")

    print()
    if blocking:
        print(f"SECRETS SCAN: FAIL -- {len(blocking)} credential-shaped "
              f"strings in tracked files.")
        return 1
    if seen:
        print(f"SECRETS SCAN: PASS (no credentials). {len(seen)} review items "
              f"remain; see HARNESS_RELEASE_AUDIT.md.")
    else:
        print("SECRETS SCAN: PASS -- no credentials, no unreviewed items.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
