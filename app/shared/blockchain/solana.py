from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from app.shared.blockchain.interfaces import BlockchainTransaction


class SolanaDevnetAdapter:
    def __init__(self, rpc_url: str) -> None:
        self._rpc_url = rpc_url

    async def get_transaction(self, signature: str) -> BlockchainTransaction | None:
        response = await asyncio.to_thread(self._fetch_transaction, signature)
        result = response.get("result")
        if result is None:
            return None
        return _parse_transaction(signature, result)

    def _fetch_transaction(self, signature: str) -> dict[str, Any]:
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    signature,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self._rpc_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("Unable to fetch Solana transaction") from exc


def _parse_transaction(signature: str, result: dict[str, Any]) -> BlockchainTransaction:
    meta = result.get("meta") or {}
    transaction = result.get("transaction") or {}
    message = transaction.get("message") or {}
    account_entries = message.get("accountKeys") or []
    account_keys = [_account_key(entry) for entry in account_entries]
    signers = [
        key
        for entry in account_entries
        if (key := _account_key(entry)) and isinstance(entry, dict) and entry.get("signer") is True
    ]
    return BlockchainTransaction(
        signature=signature,
        network="devnet",
        exists=True,
        succeeded=meta.get("err") is None,
        slot=result.get("slot"),
        block_time=result.get("blockTime"),
        signers=signers,
        account_keys=[key for key in account_keys if key],
        token_balance_deltas=_token_balance_deltas(meta, account_keys),
        raw=result,
    )


def _account_key(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        pubkey = entry.get("pubkey")
        return pubkey if isinstance(pubkey, str) else ""
    return ""


def _token_balance_deltas(meta: dict[str, Any], account_keys: list[str]) -> dict[str, int]:
    pre = _balances_by_account(meta.get("preTokenBalances") or [], account_keys)
    post = _balances_by_account(meta.get("postTokenBalances") or [], account_keys)
    addresses = set(pre) | set(post)
    return {address: post.get(address, 0) - pre.get(address, 0) for address in addresses}


def _balances_by_account(entries: list[dict[str, Any]], account_keys: list[str]) -> dict[str, int]:
    balances: dict[str, int] = {}
    for entry in entries:
        account_index = entry.get("accountIndex")
        if not isinstance(account_index, int) or account_index >= len(account_keys):
            continue
        amount = ((entry.get("uiTokenAmount") or {}).get("amount")) or "0"
        try:
            balances[account_keys[account_index]] = int(amount)
        except (TypeError, ValueError):
            balances[account_keys[account_index]] = 0
    return balances
