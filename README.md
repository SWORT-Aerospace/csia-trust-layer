# XSYS-001 confirmatory raw data (durable copy)

This orphan branch holds the raw flight data of the XSYS-001 confirmatory
campaign. Its only purpose is durable storage, so it shares no history with
the code branches. The frozen confirmatory result is on branch
`claude/code-reviewer-repo-export-zicovg`, at commit `2ac7300`:

- the report is `docs/research/XSYS_001_CONFIRMATORY_RESULT.md`;
- the result manifest `research/xsys_001_confirmatory_campaign/CONFIRMATORY_RESULT_MANIFEST.json`
  has sha256 `03f4fbfce57215d03efa47072ef1b5abcca40eb5818a445b8f19f9b76197984d`.

Nothing here changes that result.

## Contents

| path | what |
|---|---|
| `flights_xz/` | the 66 ULogs, compressed with `xz -9e`, lossless |
| `trial_records/` | the executor's 66 per-flight trial records |
| `console_logs/` | the 66 per-flight PX4 console logs |
| `campaign_records/` | `CAMPAIGN.json`, `EXECUTION_LOG.jsonl`, `executor.log`, start/end times, the sealed `CAMPAIGN_COMPLETION.json` (+ `.sha256`) and `RAW_DATA_MANIFEST.json` |
| `verify_raw_data.py` | a standard-library verifier |
| `SHA256SUMS` | the SHA-256 of every file on this branch except itself |

The uncompressed ULogs (4.60 GB) are not stored. Each xz archive
decompresses to exactly the raw ULog recorded in the sealed completion record.
`python3 verify_raw_data.py` checks every one. With
`--restore <dir>`, it also writes the `.ulg` files back.

Not included: the PX4 per-flight working directories. They are the
simulator's scratch root file systems, not evidence, and no analysis read
them.

## Integrity chain

| item | SHA-256 |
|---|---|
| `CAMPAIGN_COMPLETION.json` (sealed before stage 0) | `03265374ef446a81b4b4ae38ee482cbefea4ce1046090d2b0d2610ff9b0c334c` |
| `RAW_DATA_MANIFEST.json` | `19cb3e4b39116558767990480e1ff2f961f7ac3b9b5316bad56b4c2215095531` |

The completion record lists, for every flight, the raw ULog SHA-256 and the
xz SHA-256. The raw-data manifest lists every raw file and its hash.
