from __future__ import annotations

import base64
import binascii

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from app.core.exceptions.domain import UnauthorizedError

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class InvalidWalletSignatureError(UnauthorizedError):
    code = "INVALID_WALLET_SIGNATURE"


def verify_solana_signature(wallet_address: str, message: str, signature: str) -> None:
    public_key = _decode_base58(wallet_address)
    if len(public_key) != 32:
        raise InvalidWalletSignatureError("Invalid wallet public key")
    signature_bytes = _decode_signature(signature)
    try:
        VerifyKey(public_key).verify(message.encode("utf-8"), signature_bytes)
    except BadSignatureError as exc:
        raise InvalidWalletSignatureError("Wallet signature verification failed") from exc


def _decode_signature(value: str) -> bytes:
    decoders = (_decode_base58, _decode_base64, _decode_hex)
    for decoder in decoders:
        try:
            decoded = decoder(value)
        except ValueError:
            continue
        if len(decoded) == 64:
            return decoded
    raise InvalidWalletSignatureError("Invalid wallet signature encoding")


def _decode_base58(value: str) -> bytes:
    number = 0
    for char in value:
        try:
            number = number * 58 + BASE58_ALPHABET.index(char)
        except ValueError as exc:
            raise ValueError("Invalid base58 value") from exc
    combined = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    pad = 0
    for char in value:
        if char == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + combined


def _decode_base64(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except binascii.Error as exc:
        raise ValueError("Invalid base64 value") from exc


def _decode_hex(value: str) -> bytes:
    try:
        return bytes.fromhex(value.removeprefix("0x"))
    except ValueError as exc:
        raise ValueError("Invalid hex value") from exc
