# Your turn — the five exercises, done

Tests first (`tests/test_your_turn.py`), then the code. `pytest -q` → 33 passed; `pytest -q --controls=off` still shows the starter's four lab failures.

| Lab | Exercise | Where | The decision |
|---|---|---|---|
| 1 | Refunds of $20 or less skip approval | `controls/approvals.py` · `SMALL_REFUND_CENTS`, `policy_waiver()` · `agent.py` | The number lives in **code**, not release config: Lab 4's v2 hid a limit change in `tools.json` under a "tone" changelog, and a waiver in config would ship the same way. The business owner proposes it, risk and compliance sign it, and it changes only through a reviewed diff. Every waived call is traced as approved by `policy` with the note, never as a gap. |
| 2 | Move the scope check into the database layer | `db.py` · `CustomerDB.scoped_to()`, `ScopedDB`, `OutOfScope` · `tools.run_tool()` · `agent.py` | With scoped access on, tools get a view of the database bound to the conversation's customer, so a new tool that calls its argument `account` instead of `customer_id` is still refused (`out_of_scope`) and the other record is never read. The argument check stays as the cheap first line, so nobody is asked to approve a call that can never run. |
| 3 | Redact email addresses before the trace | `controls/traces.py` · `redact()` | Applied to every field as the line is written; the database is untouched. Traces are read by more people, for longer, than the database. |
| 4 | `release.py deploy` runs the tests and refuses on failure | `release.py` · `preflight()`, `REFUND_CEILING_DOLLARS` · `tests/conftest.py --candidate` · `test_release_gate_refund_limit_is_within_policy` | The tests run against the candidate in their own temporary state; nothing live changes until they pass. The gate test encodes the $100 ceiling, so `deploy v2` is refused. `--skip-tests` exists and is logged, because a kill switch sometimes needs a hotfix. |
| 5 | Flag an irreversible call the customer never asked for | `controls/approvals.py` · `ASKED_FOR`, `unrequested()`, `ApprovalRequest.flag` · `Decision.flag` | The customer's own message must contain a word that asks for the action; otherwise the approver sees `WARNING: the customer did not ask for this …` before deciding, and the trace carries the flag. The injected $95 refund (Lab 5) is flagged; a requested $40 refund is not. |

Demo: `echo n | python chat.py --customer C-1003 "What's my balance?"` shows the warning; `python release.py deploy v2` is refused.
