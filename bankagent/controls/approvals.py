"""Lab 1: irreversible tools wait for a human yes/no.

The agent builds an ApprovalRequest and hands it to an Approver. Anything that
can answer decide() works: a terminal prompt (here), a ticket queue, a chat
message with two buttons. In production the answer usually comes back later,
not in the same call, but the contract is the same: a request goes out, and a
yes or no comes back with a name attached.

The request carries what the customer actually said. An approver who only sees
"Refund $95.00 to C-1003" will say yes. One who also sees that the customer
asked for their balance will spot a refund nobody asked for (Lab 5).
"""

from __future__ import annotations

import getpass
import re
from dataclasses import dataclass
from typing import Protocol

from ..db import dollars
from ..tools import ToolError, describe, to_cents

# Lab 1 (your turn): refunds of this much or less run without a human.
# Who picks the number: the business owner proposes it, risk and compliance sign
# it, and it changes only through a reviewed code change — not through a release.
# Lab 4 showed why: release v2 raised the refund limit from $100 to $10,000 in a
# tools.json edit whose changelog said "tone". A waiver in config would ship the
# same way. In code, the change is a diff someone has to approve, and the trace
# records every waived call as approved by "policy", never as a gap.
SMALL_REFUND_CENTS = 20_00

# Lab 5 (your turn): words the customer's own message must contain for an
# irreversible action to count as asked for. Anything else is flagged for the
# approver before they decide; the instruction probably came from the data.
ASKED_FOR = {
    "issue_refund": re.compile(r"refund|charge|fee|credit|money|\$\s?\d", re.IGNORECASE),
    "close_account": re.compile(r"\bclos(e|ing)\b|cancel|shut", re.IGNORECASE),
}


def policy_waiver(tool: str, args: dict) -> str | None:
    """Lab 1 (your turn): the note explaining why no human is needed, or None."""
    if tool != "issue_refund":
        return None
    try:
        cents = to_cents(args.get("amount"))
    except ToolError:
        return None
    if cents <= SMALL_REFUND_CENTS:
        return f"policy: refunds of ${dollars(SMALL_REFUND_CENTS)} or less do not need approval (this one: ${dollars(cents)})"
    return None


def unrequested(tool: str, customer_said: str) -> str | None:
    """Lab 5 (your turn): a warning when the customer's message never asked for this action."""
    pattern = ASKED_FOR.get(tool)
    if pattern is None or pattern.search(customer_said or ""):
        return None
    return (f"the customer did not ask for this: they said \"{customer_said}\" — "
            f"the instruction to {tool.replace('_', ' ')} came from somewhere else (the data?)")


@dataclass(frozen=True)
class ApprovalRequest:
    tool: str
    args: dict
    customer_id: str  # the customer this conversation is bound to
    release: str      # the release that proposed the action
    customer_said: str = ""  # the customer's latest message, so the approver can compare

    def summary(self) -> str:
        return describe(self.tool, self.args)

    @property
    def flag(self) -> str | None:
        """Lab 5 (your turn): set when the customer's message never asked for this action."""
        return unrequested(self.tool, self.customer_said)


@dataclass(frozen=True)
class Decision:
    approved: bool
    approver: str  # who decided; this ends up in the trace
    note: str = ""
    flag: str | None = None  # Lab 5 (your turn): the warning the approver saw, if any


class Approver(Protocol):
    def decide(self, request: ApprovalRequest) -> Decision: ...


class ConsoleApprover:
    """Asks whoever is at the terminal. Anything other than y is a no."""

    def __init__(self, name: str | None = None) -> None:
        self.name = name or getpass.getuser()

    def decide(self, request: ApprovalRequest) -> Decision:
        print(f"\n  APPROVAL NEEDED: {request.summary()}")
        if request.customer_said:
            print(f"  The customer said: \"{request.customer_said}\"")
        if request.flag:
            print(f"  WARNING: {request.flag}")
        print(f"  (conversation bound to {request.customer_id}, release {request.release})")
        try:
            answer = input("  Approve? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        print()
        return Decision(answer in ("y", "yes"), approver=f"console:{self.name}", flag=request.flag)


class AutoApprover:
    """Gives the same answer every time and keeps every request. For tests and scripted runs."""

    def __init__(self, approve: bool, name: str = "auto-approver") -> None:
        self.approve = approve
        self.name = name
        self.requests: list[ApprovalRequest] = []

    def decide(self, request: ApprovalRequest) -> Decision:
        self.requests.append(request)
        return Decision(self.approve, approver=self.name, note="automatic", flag=request.flag)
