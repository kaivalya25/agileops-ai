# Evaluation

The full comparison ran against 60 labeled synthetic reporting cases. The fixture generator supplies 30 normal, 10 ambiguous, 5 impossible, 5 conflicting and 10 malicious cases. Run `python -m agileops.evaluation --dataset` to inspect the inputs and expected diagnoses. Run `python -m agileops.evaluation --all-modes` to reproduce the comparison with a built knowledge index and running Ollama.

The raw, naive RAG and advanced RAG modes used Qwen2.5 0.5B through Ollama. The naive mode retrieved the top three semantic chunks. The advanced mode used metadata-capable hybrid retrieval and cross-encoder reranking. The investigator used the current incident's structured diagnostics, a supported-code check and evidence from the runbooks and prior incidents.

| Mode | Correct diagnosis or abstention | Correct abstention | Correct malicious case | Valid evidence | Errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw local model | 10/60 | 0/25 | 2/10 | N/A | 3 |
| Naive RAG | 13/60 | 0/25 | 2/10 | 0% | 0 |
| Advanced RAG | 9/60 | 0/25 | 1/10 | 0% | 0 |
| Evidence-grounded investigator | 60/60 | 25/25 | 10/10 | 100% | 0 |

Accuracy compares the emitted code with the expected code or null. Evidence is scored for emitted claims that have a reference set. It requires a citation ID from a source that supports the selected diagnosis code. Errors count invocations that did not return a usable typed response.

The model frequently emitted a diagnosis for cases without enough evidence. Reranking retrieved relevant material, but the model still picked wrong codes and failed to cite supporting chunks. The investigator has an advantage on this benchmark because it reads the synthetic diagnostics and implements the same failure vocabulary. These results apply to the synthetic cases and the specific model and corpus tested.

## Retrieval

On six hand-labeled questions using the packaged corpus, hybrid search with cross-encoder reranking measured Recall@3 of **1.00**, Precision@3 of **0.39**, and MRR of **0.89**. The SOP question ranked its expected source third. The missing-column question retrieved both the runbook and the historical incident. Three retrieved slots often contain only one labeled relevant document.

Recall@K is the fraction of labeled relevant sources retrieved. Precision@K uses K as the denominator. MRR averages the reciprocal rank of the first relevant source. These metrics describe a small, closed corpus. Semantic search will still return nearby text for an unrelated question, so downstream evidence checks remain necessary.

## Workflow and security

Integration tests cover checkpoint recovery between approvals, the required operator token, SQL identifier rejection, malicious ticket and log text, fabricated citations, instructions inside retrieved documents, and rejection of a tampered QA script. The end-to-end lab completed the reporting patch and reconciled three orders before recording the recovered refresh. The [demo](demo.md) shows the observed review and delivery output.

The dependency scan reported known issues in the original pip version. Updating the workspace installer to pip 26.3 removed those findings. The local project itself was outside the public advisory database, so its behavior is covered by the static and regression checks.

See the [case-level benchmark output](demo/benchmark.json) for all measured outcomes.
