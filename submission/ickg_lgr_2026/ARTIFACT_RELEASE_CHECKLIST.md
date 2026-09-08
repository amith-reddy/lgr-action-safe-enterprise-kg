# Artifact release checklist

Release: `evomem-enterprise-v3.0.0`

- [x] Select and add a code license. MIT; see `LICENSE` at the package root.
- [x] Select and add a benchmark/data license. MIT, the same terms as the code, in a separate `LICENSE-DATA` file. `LICENSE` is kept as verbatim MIT so automated license detection recognizes the repository; `LICENSE-DATA` names the generated benchmark data and recorded outputs as its subject.
- [ ] Freeze the manuscript commit or source-archive hash.
- [x] Run `python3 scripts/reproduce_lgr_release.py --force` against the frozen release.
- [x] Confirm frozen source hashes are unchanged.
- [x] Include schemas, configurations, seeds, label specification, validation-only interpreters, conformance tests, per-task results, and figure/table sources.
- [x] Build an archive and reproduce it in an empty directory.
- [ ] Create the public repository release only after the author approves publication.
- [ ] Deposit that release in an archival repository if desired and record the real DOI. `.zenodo.json` is prepared with title, author, keywords, and license so the upload is one step; **no deposit has been made and no DOI is claimed.** Depositing publishes the artifact under the author's account and is the author's action, not an automated one.
- [ ] Replace every pending repository/DOI marker in the manuscript and data-availability statement.
- [ ] Link any SSRN preprint to the final journal DOI after acceptance.

Licenses are now selected (MIT for code in `LICENSE`, MIT for benchmark data in `LICENSE-DATA`). No public repository or DOI is claimed until the corresponding item is completed.

Verified release archive: `lgr_jws_artifact_v3.0.0.tar.gz`.
`artifact_archive_report_v3.0.0.json` records its size and SHA-256 digest, a
clean-extraction manifest check, and a successful frozen-release reproduction.
Rebuild the archive after selecting licenses or changing any included file:

```
python3 scripts/build_lgr_artifact.py --release-candidate final --force
```

## Release history

`rc1` (`lgr_jws_artifact_rc1.tar.gz`, `artifact_archive_report.json`) is retained
unchanged for provenance. **Do not distribute it:** it packages the pre-review
code, in which two independent cross-checks were weaker than the operator they
corroborate. Cite and distribute `rc2`.

`v3.0.0` is the archival release, built from the same tree as `rc2` and
carrying the ten-page manuscript. It supersedes `rc1` with three review
corrections, all covered by new regression tests:

1. The composed comparator and the action-label interpreter now enforce the
   workflow-membership source restriction themselves, instead of accepting any
   record that carries a case identifier. Previously a record from a source not
   trusted for `workflow_state` could enrol an unrelated account into a case and
   admit a refund the operator blocks. Comparator agreement is unchanged
   (100/100 evidence, 40/40 action).
2. The evidence checker now derives task-specific required answers for
   contradiction-handling and audit tasks as well, from independently resolved
   evidence rather than from the recorded label, so deleting a unique-winner
   answer from every duplicated stage field is reported instead of silently
   moving the task into the permitted population.
3. Figure 4 now plots all thirteen nonzero feature--metric changes; two were
   previously omitted while the caption asserted the omitted set was empty.

`rc2` also carries manuscript corrections from the same review, none of which
change any measured value: the Section VI test count now reads 23 further tests
and 57 total (the 34-case operator suite count is unchanged); Algorithm 1 resolves
the action target after conflict resolution as `ActionTarget(q, B, T)`, matching
Section III-C and the implementation; the Section III-D statement of retrieval
correctness now matches the Section IV-A metric definition; `KG` and `SLA` are
expanded at their first editable use; and Figure 4's caption says "top two rows".

One flagged correction is **not** applied: a citation-scope overstatement in the
locked Section I. Under the standing lock on the abstract and Sections I--II, it
is filed as a proposed patch in `JWS_REVIEW_TRIAGE_AND_IMPLEMENTATION.md` and
awaits author approval. The abstract and Sections I--II are byte-for-byte
identical to `rc1`.

The benchmark data, gold labels, and every accuracy metric are byte-identical
between `rc1` and `rc2`; only wall-clock latency fields differ between runs.
