# Standalone LLM Provider Package Release Trace

> Status: external 0.1.0 released; Taskweavn cutover verified / review pending
>
> Updated: 2026-08-12

## Outcome

Reusable synchronous provider behavior moved to the standalone MIT package
`llm-provider-adapter` (`llm_provider_adapter`). Version `0.1.0` supports
OpenAI, Claude, DeepSeek, OpenRouter, and LiteLLM through one immutable chat,
retry, error, capability, and safe telemetry contract.

Taskweavn now consumes the public package through the bounded dependency
`llm-provider-adapter[all]>=0.1.0,<0.2.0`, keeps product assembly and legacy
OpenHands completion/token-counting, and removes duplicate provider transport,
conversion, parsing, and retry implementation.

## Confirmed product decisions

| Decision | Value |
|---|---|
| Distribution | `llm-provider-adapter` |
| Import package | `llm_provider_adapter` |
| License | MIT |
| First release | `0.1.0` |
| Consumer range | `>=0.1.0,<0.2.0` |
| Release sequence | TestPyPI verification, then the same artifact to public PyPI |

Requirements handoff:
`d52e1431b96b3d587b6fa2a8b986dd8c88f2db767a6509a50f5a1e3ac4e34b3d`.
Confirmed requirements commit: `4406f72f6e944e64e543f016da48283d7dfbdd7d`.

## External repository proof

Repository: `https://github.com/zhanghao1903/llm-provider-adapter`.

| Stage | Immutable proof |
|---|---|
| Package PR #1 reviewed head | `4bb533672e2eb3c2b7f732c2bdacbdfdbd2141fd` |
| Package PR #1 merge/main | `c7b40207a1cbe1216f7669eb1a761d3a921f49a2` |
| Release-controller PR #2 reviewed head | `108277e436c811f0679f2a414260de64a481f177` |
| Release-controller PR #2 merge/main | `19e7526086c8306b5823c17fb4d5e5eba60e800d` |
| Publish workflow run | `31506383555`, completed/success |
| Wheel SHA-256 | `43a0526133087d6d06897cd781a5732e337345b55b11b79a16c3bf5f4531d868` |
| Sdist SHA-256 | `d84fc296a239417aa46616f385b6eab8ec2e53c1f067453ce2a591a036c1aa63` |

The workflow built once, uploaded that artifact set to TestPyPI, verified exact
registry filenames/digests and seven isolated environments, then uploaded the
same artifact set through the protected public PyPI environment. Public PyPI
metadata and a fresh Python 3.12 `[all]` installation reproduced the exact
hashes, constructed all five providers offline, and ran `examples/fake_chat.py`.

The first public job attempt remained queued without a runner and was canceled
only after confirming public PyPI still returned 404 and the artifact hashes
were unchanged. A manual credential fallback was rejected by PyPI before any
file upload; public PyPI remained empty. Re-running only the canceled protected
job used OIDC and completed the authorized publication. No tag or GitHub Release
was created.

## Taskweavn cutover

- external package models/errors/retry/providers are exact compatibility re-exports;
- product Settings, secrets, Agent profiles, usage, diagnostics and logs remain local;
- `LLMProvider` is chat-only while `LLMClient` keeps OpenHands
  `complete()`/`count_tokens()`;
- package nested values stay recursively immutable; Taskweavn explicitly uses
  `to_dict()` when it needs a mutable JSON transcript;
- package telemetry is adapted through a safe allow-list and never carries raw
  prompt, tool arguments, headers, arbitrary metadata, payloads, or exceptions;
- direct SDK dependencies and duplicate provider source are removed.

Compatibility re-exports remain through one Taskweavn minor window and are not
eligible for removal before Taskweavn `0.3.0` without a separate breaking-change
review.

## Verification and remaining closure

Taskweavn consumer verification passed:

- complete backend suite: `1604 passed, 1 skipped`;
- changed Python scope Ruff: passed;
- changed production/boundary strict Mypy: passed;
- `uv lock --check`: passed;
- `git diff --check`: passed;
- duplicate provider source audit: no matches.

Before this record becomes `done`, the exact Taskweavn PR head still requires
independent review, merge proof, and lifecycle post-merge traceability.

Rollback means reverting the Taskweavn consumer commit and lock. The immutable
public `0.1.0` release must not be deleted or overwritten, and provider source
must not be copied back into Taskweavn as a rollback shortcut.
