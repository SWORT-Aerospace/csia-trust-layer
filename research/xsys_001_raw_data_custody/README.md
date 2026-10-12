# XSYS-001 raw data: durable custody

**Status: DURABLE_STORAGE_COMPLETE.**

The raw flight data of the XSYS-001 confirmatory campaign is stored on the
orphan branch `claude/xsys-001-raw-data` of this repository, at commit
`3f2ccae7afd66552b8b06e1efde4cf666bf0bf22`. The owner authorized a separate
raw-data branch so that 0.81 GB of archives stays out of the code branch's
history.

`DURABLE_STORAGE_RECORD.json` holds the full custody record. For every
flight, it gives:

- the raw ULog SHA-256 and size;
- the xz archive path, SHA-256 and size on the branch;
- whether the branch copy matches the sealed completion record.

For all 66 flights, it does.

The branch holds the 66 lossless `xz -9e` archives of the ULogs, not the
4.60 GB of uncompressed ULogs. Each archive decompresses to exactly the raw
ULog hash in the sealed
`research/xsys_001_confirmatory_campaign/CAMPAIGN_COMPLETION.json`. The
branch's `verify_raw_data.py` checks all 66 and can restore the `.ulg` files.

**Relation to the frozen result.** The confirmatory result, frozen at commit
`2ac7300`, records `DURABLE_STORAGE_PENDING`, because that was true when it
was frozen. It is not edited. This directory records what happened after the
freeze and binds itself to the frozen manifests by hash.
