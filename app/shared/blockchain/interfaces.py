from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class BlockchainTransaction:
    signature: str
    network: str
    exists: bool
    succeeded: bool
    slot: int | None = None
    block_time: int | None = None
    signers: list[str] = field(default_factory=list)
    account_keys: list[str] = field(default_factory=list)
    token_balance_deltas: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_proof(self) -> dict[str, Any]:
        return {
            "signature": self.signature,
            "network": self.network,
            "exists": self.exists,
            "succeeded": self.succeeded,
            "slot": self.slot,
            "block_time": self.block_time,
            "signers": self.signers,
            "account_keys": self.account_keys,
            "token_balance_deltas": self.token_balance_deltas,
        }


class BlockchainClientInterface(Protocol):
    async def get_transaction(self, signature: str) -> BlockchainTransaction | None: ...
