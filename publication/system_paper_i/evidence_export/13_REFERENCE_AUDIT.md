# 13 — Reference audit

**No bibliography metadata was fabricated to produce this file.** Every row is
read from `papers/csia_systems/refs.bib` at commit
`e95b0ea7c7f078a1acc372daa33948751b77cdad`.

**Classification counts:** VERIFIED_EXISTENCE **0** · VERIFIED_CONTENT **0** ·
RELEVANCE_CONFIRMED **0** · FROM_PRIOR_BRIEF_ONLY **9** ·
REMOVE **2**.

**Not one entry has been verified against a publisher record.** That is the
state of the bibliography, not a limitation of this audit.

| key | cited in main.tex | title | carries VERIFY | reconstructed | class | why |
|---|---|---|---|---|---|---|
| `dong2024statedependent` | yes | Verification of diagnosability for discrete- | yes | no | **FROM_PRIOR_BRIEF_ONLY** | metadata supplied by a brief, not checked against the publisher record |
| `carvalho2012intermittent` | yes | Robust diagnosis of discrete event systems a | no | no | **FROM_PRIOR_BRIEF_ONLY** | metadata supplied by a brief, not checked against the publisher record |
| `carvalho2013permanent` | yes | Robust diagnosis of discrete-event systems a | no | no | **FROM_PRIOR_BRIEF_ONLY** | metadata supplied by a brief, not checked against the publisher record |
| `takai2021diagnosability` | **no** | **VERIFY: title not supplied by the brief** | yes | no | **REMOVE** | not cited anywhere in main.tex |
| `yin_phidiagnosability` | yes | Uniform $\varphi$-diagnosability of discrete | yes | yes | **FROM_PRIOR_BRIEF_ONLY** | reconstructed from brief prose |
| `krysander2024multimode` | yes | **VERIFY: title not supplied by the brief** | yes | no | **FROM_PRIOR_BRIEF_ONLY** | title itself unverified |
| `krysander2008sensorplacement` | yes | Sensor placement for fault diagnosis | no | no | **FROM_PRIOR_BRIEF_ONLY** | metadata supplied by a brief, not checked against the publisher record |
| `hurdle2007faulttree` | yes | Fault diagnostics of dynamic system operatio | yes | no | **FROM_PRIOR_BRIEF_ONLY** | metadata supplied by a brief, not checked against the publisher record |
| `reeves2019sensorselection` | yes | **VERIFY: title not supplied by the brief** | yes | no | **FROM_PRIOR_BRIEF_ONLY** | title itself unverified |
| `kang2024gnss` | **no** | **VERIFY: title not supplied by the brief** | yes | no | **REMOVE** | not cited anywhere in main.tex |
| `blanke2003ftc` | yes | Diagnosis and Fault-Tolerant Control | yes | yes | **FROM_PRIOR_BRIEF_ONLY** | reconstructed from brief prose |

---

## What each proposed source is being asked to support

The claim attributed to each source was read from `main.tex`. Where the
attributed claim is broader than what a title alone can support, that is
stated.

| source | claim attributed in main.tex | what is verified here |
|---|---|---|
| Carvalho / Basilio / Moreira, intermittent and permanent | robust diagnosis of discrete-event systems against intermittent and permanent loss of observations | **titles only, from a brief.** The paper cites them for the existence of a treatment of observation loss. That is consistent with the titles. Nothing about their specific results has been checked. |
| Yin / Gao / Li, phi-diagnosability | diagnosability under state-dependent observation | **RECONSTRUCTED from brief prose.** Author list, title, venue and year all require verification. The paper must not attribute a specific theorem to this entry until it is resolved. |
| Dong / state-dependent | verification of diagnosability for DES with state-dependent observation | title rendered from a brief; volume, number and pages unverified |
| Krysander / Hashemniya, multimode; Krysander / Frisk, sensor placement | structural isolability with mode-dependent behaviour; sensor placement for fault diagnosis | one entry's **title is itself `VERIFY`**. Sensor-placement relevance is plausible from the title but unconfirmed |
| Hurdle / Reeves, fault tree and sensor selection | fault-tree and sensor-selection background | Hurdle's title was reconstructed from WP-C5 brief prose; Reeves' title is `VERIFY` |
| Antonante / Spivak / Carlone | **NOT PRESENT in refs.bib** | this source is proposed in prior discussion but has no bib entry and is cited nowhere. If the paper wants it, it must be added and verified from scratch |
| Gertler | **NOT PRESENT in refs.bib** | same |
| Little & Rubin | **NOT PRESENT in refs.bib** | same. Note: a missing-data citation would attach to the *mathematical* paper's coarsening argument, not to this systems paper |
| Blanke et al., Diagnosis and Fault-Tolerant Control | standard FTC reference | RECONSTRUCTED; edition, year and publisher location all `VERIFY`, and a later edition exists |

---

## What remains for a human or a literature session

1. **Resolve every entry against the publisher record** (DOI, title, authors,
   venue, year, pages). 9 entries.
2. **Delete or cite** the 2 uncited entries.
3. **Decide on the three sources with no bib entry at all**
   (Antonante/Spivak/Carlone, Gertler, Little & Rubin): add and verify, or
   drop from the plan.
4. **Re-read each source enough to confirm the attributed claim**, not just
   that the paper exists. No entry currently has VERIFIED_CONTENT.

**This environment cannot do steps 1 and 4.** There is no local full text for
any of these works and no verified external lookup is available here. The
export states this rather than guessing.

`tools/publication/bib_guard.py` fails the build until step 1 is done.
