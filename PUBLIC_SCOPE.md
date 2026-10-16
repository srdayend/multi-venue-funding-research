# Public scope and provenance

Prepared 2026-10-16 from private development snapshot `ffb608310f180c6017b0d896d4b04c45ce352bdc`.

## Included

Original domain models, asset mapping registry, quality/quarantine code, corresponding unit tests, and reviewed asset-mapping policy. Source and existing tests are copied without behavioral edits. Packaging, documentation and the synthetic settlement example are prepared specifically for this excerpt.

The mapping configuration contains instrument identifiers, conversion factors and review policy; these are historical research decisions, not a current trading whitelist or proof that instruments remain listed.

## Excluded

Private Git history; deployment settings; infrastructure endpoints; storage credentials; environment files; collected market archives; account/trade history; exchange clients; collection orchestration; live execution; full research datasets. No original repository visibility is changed.

## Evidence boundary

The 604-event inventory and related counts are reported from versioned private research notes, not independently recomputed from raw archives in this excerpt. They describe the September 12–15, 2026 local snapshot, not the current collection total. Unit-test success proves only tested model/validation behavior.

## Security review boundary

Every candidate file is reviewed and scanned for recognizable credentials, private infrastructure paths, account data and copyright headers. No secret values were identified in the selected files. This is a bounded source review, not a guarantee that no secret can exist. The complete private repository and its reachable legacy history have NOT been audited. They are excluded, and a future public repository must start with a fresh initial commit. Never mirror or push the original private Git history.

## Authorship and license boundary

The excerpt has standard-library runtime imports only. No third-party strategy source or copyright header was identified in these selected modules. This does not prove independent authorship. Development used AI coding tools. No new project-wide open-source license is granted by this release candidate. Any later licensing choice must respect actual ownership and any third-party notices. The separate `funding-arb-system` repository is not used as a source for this release.
