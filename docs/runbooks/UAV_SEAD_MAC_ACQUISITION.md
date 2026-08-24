# UAV-SEAD acquisition — Mac operator runbook

This walks you through downloading the UAV-SEAD flight dataset onto the
external SSD and proving the download is complete and untampered.

You do not need to know Git, Python, or Unix. Copy each block, paste it into
Terminal, press Return, and read what comes back. **If any step prints
`BLOCKED` or `blocker:`, stop and read [Part 12](#12-when-something-goes-wrong)
— do not continue past a blocker.**

Two rules the tooling enforces for you, so you cannot get them wrong:

- Nothing is downloaded until you type the confirmation token `UAV-SEAD`.
- No dataset file is ever written inside the code folder.

**Fixed values used throughout**

| Thing | Value |
| --- | --- |
| Code folder | `$HOME/swort/csia-trust-layer` — `$HOME` is your own home folder, so no username is written down here |
| External SSD | `/Volumes/CSIA_DATA` |
| Data root | `/Volumes/CSIA_DATA/CSIA_DATA_LAKE` |
| Dataset | `aykutkabaoglu/uav-flight-anomaly-dataset` (DOI `10.57967/hf/7772`, CC-BY-4.0) |

**Two placeholders you will fill in from live output**

| Placeholder | Where you get it |
| --- | --- |
| `<RESOLVED_HF_COMMIT>` | Printed by **step 6 (preflight)** as `resolved commit`. Also saved in `/Volumes/CSIA_DATA/CSIA_DATA_LAKE/reports/uav_sead_preflight.json`. |
| `<AGGREGATE_MANIFEST_HASH>` | Printed by **step 11 (verify)** as `aggregate_sha256`. Also the folder name under `/Volumes/CSIA_DATA/CSIA_DATA_LAKE/raw/uav_sead/`. |

Only type these in if a command below explicitly shows the placeholder.
Most commands find the values themselves.

---

## 1. Open Terminal

Press `Command` + `Space`, type `Terminal`, press `Return`. A window with a
text prompt opens. That is where every block below goes.

## 2. Plug in and check the SSD

Connect the CSIA_DATA drive, wait for the Finder icon, then:

```bash
ls -d /Volumes/CSIA_DATA && df -h /Volumes/CSIA_DATA
```

You want a line showing the drive and its free space. If you see
`No such file or directory`, the drive is not mounted — unplug, replug, wait
ten seconds, run it again.

## 3. Go to the code folder

```bash
cd "$HOME/swort/csia-trust-layer"
pwd
```

`pwd` must print a path ending in `/swort/csia-trust-layer`. If it prints
anything else, the code folder is somewhere other than `$HOME/swort/` and
every `cd` block below must be changed to match it.

## 4. Update the code

```bash
cd "$HOME/swort/csia-trust-layer"
git status --short
```

**Empty output is required to continue.** If it prints anything at all,
**stop here** and see [dirty Git tree](#dirty-git-tree). Do not stash, reset,
checkout, or delete anything to make it empty — those commands destroy work,
and whatever is uncommitted may matter.

With a clean tree:

```bash
git fetch origin
git switch claude/code-reviewer-repo-export-zicovg
git pull --ff-only origin claude/code-reviewer-repo-export-zicovg
git log --oneline -1
```

`--ff-only` means the pull either fast-forwards cleanly or fails outright —
it will never invent a merge commit or start a conflict you would have to
resolve. If it fails, stop and report the message.

## 5. Turn on the Python environment and install

```bash
source .venv/bin/activate
python --version
```

Your prompt now starts with `(.venv)`. Python should report 3.12 or newer.
If `source` fails, see [Python environment missing](#python-environment-missing).

```bash
pip install -e ".[data,dev,logs,mavlink]"
```

Then confirm every library loaded:

```bash
python -c "import duckdb, huggingface_hub, jsonschema, polars, pyarrow, pymavlink, pyulog, yaml; print('all dependencies OK')"
```

## 6. Check the machine, the SSD, and the network

```bash
python tools/run_uav_sead_mac_pipeline.py \
  --stage environment \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE
```

This checks the branch, the commit, the Python version, every dependency,
the SSD mount, free space, whether the data root sits outside the code
folder, and whether Hugging Face is reachable. It writes
`/Volumes/CSIA_DATA/CSIA_DATA_LAKE/reports/mac_environment_check.json`.

Look for `=== stage: environment -> OK ===`.

## 7. Preflight — resolve and pin the dataset version

```bash
python tools/run_uav_sead_mac_pipeline.py \
  --stage preflight \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE
```

This asks Hugging Face which exact version (commit) is current, counts the
files, adds up the download size, and compares it to your free space. It
downloads no dataset content.

**Write down the `resolved commit` value — that is `<RESOLVED_HF_COMMIT>`.**

You want `DOWNLOAD AUTHORIZED    YES`. If you see `NO`, each reason is listed
after `blocker:`.

To re-read it later:

```bash
cat /Volumes/CSIA_DATA/CSIA_DATA_LAKE/reports/uav_sead_preflight.json
```

## 8. Dry run — rehearse without downloading

```bash
python tools/run_uav_sead_mac_pipeline.py \
  --stage dry-run \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE
```

Prints how many files and bytes *would* arrive and where they would go.
Still downloads nothing.

## 9. Start the real download

This is the only step that transfers data. It can run for a long time.
Keep the Mac awake and the SSD connected.

```bash
caffeinate -i python tools/run_uav_sead_mac_pipeline.py \
  --stage acquire \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE \
  --confirm-download UAV-SEAD
```

`caffeinate -i` stops the Mac sleeping while it runs. The token
`--confirm-download UAV-SEAD` must be typed exactly, capitals included —
without it the tool refuses and downloads nothing.

## 10. Watch progress from a second window

Open a **second** Terminal window (`Command` + `N`), then:

```bash
cd "$HOME/swort/csia-trust-layer"
source .venv/bin/activate
python tools/run_uav_sead_mac_pipeline.py \
  --stage monitor \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE
```

This refreshes every 30 seconds and shows state, pinned commit, files and
`.ulg` files completed, bytes vs expected, percent complete, cache size, free
SSD space, last completed file, retries, last error, start time, elapsed
time, transfer rate and — only once enough has transferred for the estimate
to mean anything — estimated time remaining.

It needs no Homebrew and no `watch` command, which stock macOS does not ship.

Change the refresh rate with `--interval-seconds`, or take a single reading:

```bash
python tools/run_uav_sead_mac_pipeline.py \
  --stage monitor --once \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE
```

Stop watching with `Control` + `C`. That stops only the *watcher* — the
download in the other window keeps running, and the monitor never changes
acquisition state.

### Stopping the download on purpose

Click the download window, press `Control` + `C` once, and wait. Finished
files are kept. Nothing incomplete is ever promoted.

### Resuming

Exactly the same command as step 9 — it reuses what is already there:

```bash
caffeinate -i python tools/run_uav_sead_mac_pipeline.py \
  --stage acquire \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE \
  --confirm-download UAV-SEAD
```

## 11. Verify every file and lock the snapshot

```bash
python tools/run_uav_sead_mac_pipeline.py \
  --stage verify \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE
```

This confirms every expected file arrived at the right size, rejects partial
files, computes a SHA-256 for each file, builds a sorted manifest, computes
one aggregate hash over it, recomputes it to be sure, then moves the
snapshot into permanent read-only storage.

**Write down `aggregate_sha256` — that is `<AGGREGATE_MANIFEST_HASH>`.**

Check what landed:

```bash
ls -1 /Volumes/CSIA_DATA/CSIA_DATA_LAKE/raw/uav_sead/
du -sh /Volumes/CSIA_DATA/CSIA_DATA_LAKE/raw/uav_sead/*
ls -1 /Volumes/CSIA_DATA/CSIA_DATA_LAKE/manifests/uav_sead/
```

Independent re-check of the hash (uses the placeholder):

```bash
python -c "
from csia.data.snapshot import build_manifest, aggregate_hash
snap='/Volumes/CSIA_DATA/CSIA_DATA_LAKE/raw/uav_sead/<AGGREGATE_MANIFEST_HASH>'
print('recomputed:', aggregate_hash(build_manifest(snap)))
print('expected:  ', snap.rsplit('/',1)[1])"
```

The two lines must match exactly.

## 12. Check the labels file

```bash
python tools/run_uav_sead_mac_pipeline.py \
  --stage mapping \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE
```

Reads `mapping.json` and reports how many flights are mapped, how many are
annotated, whether the published figure of **1,396 annotated flights** is
reproduced exactly, plus duplicates, missing files and unreferenced files.

A mismatch is **not** an error to fix — it is a finding. Record it and report
it. The tool never repairs a discrepancy.

## 13. Freeze the partitions — before anyone looks at the data

```bash
python tools/run_uav_sead_mac_pipeline.py \
  --stage partition \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE
```

First it runs a **grouping audit**: it looks for real aircraft, campaign,
session or lineage identity in `mapping.json`, the directory layout, the file
names, and the ULog *header* fields (never flight signals). It writes
`/Volumes/CSIA_DATA/CSIA_DATA_LAKE/reports/uav_sead_grouping_audit.json`.

Then it splits the flights into DEVELOPMENT / CALIBRATION / VALIDATION and a
protected holdout, grouped so related flights stay on the same side, and
writes
`/Volumes/CSIA_DATA/CSIA_DATA_LAKE/manifests/uav_sead/partition_manifest_v1.json`.

**Read `partition_quality` in the output.** It decides what may honestly be
claimed later:

| `partition_quality` | Holdout is called | Aircraft-level claims |
| --- | --- | --- |
| `AIRCRAFT_GROUPED` | `BLIND_TEST` | allowed |
| `CAMPAIGN_GROUPED` / `SESSION_GROUPED` / `SOURCE_LINEAGE_GROUPED` | `BLIND_TEST` | **not allowed** |
| `FILE_GROUPED` | `FILE_LEVEL_HOLDOUT` | **not allowed** |
| `UNGROUPED_FLIGHT_HASH` | `UNGROUPED_HOLDOUT` | **not allowed** |

This is not a formality. Without per-aircraft identity, the same airframe can
land on both sides of the split, so results cannot show the system works on
an aircraft it has never seen. The tool renames the partition itself so
nobody downstream reads "BLIND_TEST" and claims more than the data supports.

If the audit finds files that look related but would be grouped apart, the
partition step **refuses** and prints the collisions. That is the correct
outcome — report it rather than forcing it through.

**This must happen before anybody runs CSIA, picks a threshold, or looks at
any fault signal.** Choosing the split after seeing results — even honestly —
is indistinguishable from choosing it to flatter the results. `leakage_free`
must be `True`.

## 14. Produce the certificate

```bash
python tools/run_uav_sead_mac_pipeline.py \
  --stage certificate \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE
```

Writes both:

```bash
cat /Volumes/CSIA_DATA/CSIA_DATA_LAKE/reports/UAV_SEAD_ACQUISITION_CERTIFICATE.md
```

The certificate ends with `csia_evaluation_started: false`. That stays false
until a separate evaluation slice begins. Acquisition and evaluation are
deliberately never the same run.

## 15. Confirm the code folder is still clean

```bash
cd "$HOME/swort/csia-trust-layer"
git status --short
```

Empty output is the pass. No dataset file, report, manifest or certificate
should ever appear here — they all live on the SSD.

---

## Running everything in one command

Once you have done it once, the whole sequence is:

```bash
cd "$HOME/swort/csia-trust-layer"
source .venv/bin/activate
caffeinate -i python tools/run_uav_sead_mac_pipeline.py \
  --stage all \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE \
  --confirm-download UAV-SEAD
```

Without `--confirm-download UAV-SEAD`, `--stage all` runs every check and
stops at the download, telling you exactly how to resume.

---

## 12. When something goes wrong

The safe default is always the same: **completed files are kept, evidence is
kept, promotion is refused, nothing continues silently.** Re-running the same
command is almost always the right move.

### SSD disconnected
The download stops with an I/O error. Replug the drive, confirm
`ls -d /Volumes/CSIA_DATA` works, then re-run step 9. Files already finished
are reused. If macOS remounted it as `CSIA_DATA 1`, eject and replug — do not
point the tool at the renamed volume.

### Mac goes to sleep
The transfer stalls or drops. Re-run step 9. Use `caffeinate -i` (as shown)
to prevent it.

### Ctrl-C interruption
Expected and safe. Progress records `INTERRUPTED`. Re-run step 9 to resume.

### Lost internet
Retries happen automatically with a growing wait. If it still fails, restore
the connection and re-run step 9.

### Hugging Face rate limit
`429` or "rate limit" in the log. Wait fifteen minutes and re-run step 9. If
it persists, create a free Hugging Face token and:
```bash
export HF_TOKEN=hf_your_token_here
```

### Partial cache
Never promoted. `verify` reports what is missing. Re-run step 9, then step 11.
Only if instructed to start over:
```bash
rm -rf /Volumes/CSIA_DATA/CSIA_DATA_LAKE/cache/uav_sead/<RESOLVED_HF_COMMIT>
```

### Changed upstream repository commit
The tool refuses: it will not swap the version you certified for a new one.
Re-run step 7 (preflight) to pin the new commit, note the change, then step 9.

### Insufficient free space
Preflight blocks before downloading. Free space on the SSD, or use a larger
drive, then re-run step 7.

### Mapping count mismatch
`annotated_count_matches_claim: false`. This is a finding, not a failure.
Record it in the certificate and report it. Do not edit `mapping.json`.

### Dirty Git tree
`git status --short` lists files. **Stop.** Do not stash, reset, checkout, or
delete anything — those commands can destroy work that has not been saved
anywhere else.

Copy the exact output and report it. Whoever knows what those edits were
decides what happens to them. Acquisition can wait; unrecoverable work
cannot.

### Failed hash verification
The strongest possible stop signal: the bytes on disk are not the bytes that
were published. Nothing is promoted. Keep everything, run step 11 again, and
report the exact output. Do not delete the cache.

### Failed atomic promotion
A `.materializing` folder may remain. Nothing was corrupted — the real
snapshot only appears once verified. Re-run step 11.

### Duplicate snapshot
Two hash folders under `raw/uav_sead/` means two different downloads. Say
which one you want:
```bash
python tools/run_uav_sead_mac_pipeline.py \
  --stage mapping \
  --data-root /Volumes/CSIA_DATA/CSIA_DATA_LAKE \
  --snapshot <AGGREGATE_MANIFEST_HASH>
```

### Python environment missing
`source .venv/bin/activate` fails. Rebuild it:
```bash
cd "$HOME/swort/csia-trust-layer"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[data,dev,logs,mavlink]"
```

### `.venv` using the wrong interpreter
Check with:
```bash
which python
python --version
```
`which python` must be inside `$HOME/swort/csia-trust-layer/.venv/`.
If it is not, or the version is below 3.11, delete and rebuild:
```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[data,dev,logs,mavlink]"
```

---

## What must not happen during acquisition

- Do **not** run CSIA v1 or any evaluation.
- Do **not** open, plot, or inspect flight signals before step 13.
- Do **not** choose or tune any threshold.
- Do **not** move, rename, or edit anything under `raw/uav_sead/`.

Evaluation is a separate slice that begins only after the certificate exists
and the partitions are frozen.
