"""Check every bibliography entry against the publisher record, field by field.

WHY THIS EXISTS. `refs.bib` carries 37 provenance markers. Their meaning is
narrow and specific: FROM-BRIEF-UNVERIFIED means the details came from a
trusted upstream brief and were NEVER independently checked against the
publisher. `make bib-guard` fails while any marker stands, and its message is
blunt: "Do not delete markers to make this pass."

Clearing a marker therefore requires one thing only -- comparing the entry
against the publisher's own record. This tool does that comparison
mechanically so the remaining human judgement is reading a diff rather than
retyping eleven citations.

WHAT COUNTS AS THE PUBLISHER RECORD. Crossref (`api.crossref.org`) serves
metadata deposited by the publisher itself, keyed by DOI. That is the record.
A web search result is NOT: it is a summary over snippets, which is another
unverified source, and swapping one unverified source for another while
deleting the warning is worse than leaving the warning up.

NETWORK. This tool needs `api.crossref.org`. In sandboxes where egress is
restricted it will say so and exit non-zero rather than reporting a vacuous
pass. Run it somewhere with network access.

  python tools/publication/verify_bibliography.py
  python tools/publication/verify_bibliography.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_BIB = os.path.join(ROOT, "papers", "csia_systems", "refs.bib")
CROSSREF = "https://api.crossref.org/works/"
CONTACT = "csia-bib-verify/1.0 (bibliography verification; polite pool)"

MARKERS = ("FROM-BRIEF-UNVERIFIED", "RECONSTRUCTED", "VERIFY")


# ------------------------------------------------------------------ parsing
def _strip_latex(s: str) -> str:
    """Fold LaTeX accents and braces so a name compares to a plain one.

    `Jo{\\~a}o` and `Joao` are the same author; `St{\\'e}phane` and `Stephane`
    are the same author. Without this every accented name reads as a mismatch
    and the report becomes noise nobody trusts.
    """
    s = re.sub(r"\{\\[`'\"^~=.uvHtcdbk]\s*\{?([A-Za-z])\}?\}", r"\1", s)
    s = re.sub(r"\\[`'\"^~=.]\{?([A-Za-z])\}?", r"\1", s)
    s = s.replace("{", "").replace("}", "").replace("\\", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _norm(s) -> str:
    if s is None:
        return ""
    s = _strip_latex(str(s))
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("--", "-")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def parse_bib(path):
    """{key: {"type":…, "fields":{…}, "markers":[…], "raw":…}}"""
    text = open(path, encoding="utf-8").read()
    entries = {}
    for chunk in re.split(r"\n(?=@)", text):
        m = re.match(r"@(\w+)\{([^,]+),", chunk)
        if not m:
            continue
        etype, key = m.group(1), m.group(2).strip()
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{", chunk):
            name = fm.group(1).lower()
            i, depth, buf = fm.end(), 1, []
            while i < len(chunk) and depth:
                c = chunk[i]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if not depth:
                        break
                buf.append(c)
                i += 1
            fields[name] = re.sub(r"\s+", " ", "".join(buf)).strip()
        entries[key] = {
            "type": etype, "fields": fields, "raw": chunk,
            "markers": [mk for mk in MARKERS if mk in chunk],
        }
    return entries


def cited_keys(tex_path):
    if not os.path.exists(tex_path):
        return set()
    tex = open(tex_path, encoding="utf-8").read()
    out = set()
    for grp in re.findall(r"\\cite[a-zA-Z]*\{([^}]*)\}", tex):
        for k in grp.split(","):
            out.add(k.strip())
    return out


# ---------------------------------------------------------------- crossref
def fetch_crossref(doi, timeout=25):
    req = urllib.request.Request(CROSSREF + doi,
                                 headers={"User-Agent": CONTACT,
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.loads(fh.read().decode("utf-8"))["message"]


def compare(entry, rec):
    """Field-by-field comparison. Returns {field: (status, bib, publisher)}."""
    f = entry["fields"]
    out = {}

    def cmp(name, bib_val, pub_val):
        if pub_val in (None, "", []):
            out[name] = ("PUBLISHER_SILENT", bib_val, None)
        elif not bib_val or "VERIFY" in str(bib_val):
            out[name] = ("MISSING_IN_BIB", bib_val, pub_val)
        elif _norm(bib_val) == _norm(pub_val):
            out[name] = ("MATCH", bib_val, pub_val)
        else:
            out[name] = ("MISMATCH", bib_val, pub_val)

    cmp("title", f.get("title"), (rec.get("title") or [None])[0])
    cmp("journal", f.get("journal") or f.get("booktitle"),
        (rec.get("container-title") or [None])[0])
    cmp("volume", f.get("volume"), rec.get("volume"))
    cmp("number", f.get("number"), rec.get("issue"))
    cmp("pages", f.get("pages"), rec.get("page"))
    year = None
    for k in ("issued", "published-print", "published-online"):
        dp = (rec.get(k) or {}).get("date-parts") or []
        if dp and dp[0] and dp[0][0]:
            year = dp[0][0]
            break
    cmp("year", f.get("year"), year)

    # authors: compare the ordered family-name sequence
    pub_fam = [a.get("family", "") for a in rec.get("author", []) or []]
    bib_fam = []
    for part in re.split(r"\band\b", f.get("author", "")):
        part = part.strip()
        if not part:
            continue
        bib_fam.append(part.split(",")[0].strip() if "," in part
                       else part.split()[-1])
    if not pub_fam:
        out["authors"] = ("PUBLISHER_SILENT", "; ".join(bib_fam), None)
    elif [_norm(x) for x in bib_fam] == [_norm(x) for x in pub_fam]:
        out["authors"] = ("MATCH", "; ".join(bib_fam), "; ".join(pub_fam))
    else:
        out["authors"] = ("MISMATCH", "; ".join(bib_fam), "; ".join(pub_fam))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bib", default=DEFAULT_BIB)
    ap.add_argument("--tex", default=os.path.join(
        ROOT, "papers", "csia_systems", "main.tex"))
    ap.add_argument("--json", default=None)
    ap.add_argument("--fixture", default=None,
                    help="offline JSON {doi: crossref_message} for testing")
    args = ap.parse_args()

    entries = parse_bib(args.bib)
    cited = cited_keys(args.tex)
    fixture = {}
    if args.fixture:
        fixture = json.load(open(args.fixture, encoding="utf-8"))

    report, unreachable = {}, []
    for key, e in sorted(entries.items()):
        doi = e["fields"].get("doi")
        row = {"key": key, "markers": e["markers"],
               "cited": key in cited, "doi": doi}
        if not doi:
            row["status"] = "NO_DOI_CANNOT_VERIFY_AUTOMATICALLY"
        else:
            try:
                rec = (fixture[doi] if doi in fixture
                       else fetch_crossref(doi))
                row["status"] = "COMPARED"
                row["fields"] = {k: {"status": v[0], "bib": v[1],
                                     "publisher": v[2]}
                                 for k, v in compare(e, rec).items()}
                bad = [k for k, v in row["fields"].items()
                       if v["status"] in ("MISMATCH", "MISSING_IN_BIB")]
                row["fields_needing_attention"] = bad
                row["clearable"] = not bad
            except (urllib.error.URLError, urllib.error.HTTPError,
                    OSError, KeyError, ValueError) as exc:
                row["status"] = "UNREACHABLE"
                row["error"] = f"{type(exc).__name__}: {exc}"
                unreachable.append(key)
        report[key] = row

    compared = [r for r in report.values() if r["status"] == "COMPARED"]
    clearable = [r for r in compared if r.get("clearable")]
    print("=== bibliography verification against the publisher record")
    print(f"  entries                : {len(entries)}")
    print(f"  uncited                : "
          f"{sorted(k for k, r in report.items() if not r['cited'])}")
    print(f"  without a DOI          : "
          f"{sorted(k for k, r in report.items() if not r['doi'])}")
    print(f"  compared to Crossref   : {len(compared)}")
    print(f"  unreachable            : {len(unreachable)} {unreachable}")
    print(f"  clean, marker clearable: {len(clearable)}")
    for r in compared:
        if not r.get("clearable"):
            print(f"    {r['key']}: {r['fields_needing_attention']}")
            for fld in r["fields_needing_attention"]:
                d = r["fields"][fld]
                print(f"        {fld:9s} bib={d['bib']!r}")
                print(f"        {'':9s} pub={d['publisher']!r}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, sort_keys=True, default=str)
        print(f"-> {args.json}")

    if unreachable:
        print("\n  !! Entries could not be checked against the publisher.")
        print("     A marker must NOT be cleared for any of them. Re-run "
              "where api.crossref.org is reachable.")
        return 2
    return 0 if len(clearable) == len(compared) else 1


if __name__ == "__main__":
    sys.exit(main())
