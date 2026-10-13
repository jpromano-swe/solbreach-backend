from typing import Literal

from pydantic import BaseModel, Field


class MintAuthorizationRequest(BaseModel):
    player: str = Field(min_length=32, max_length=44)
    level: int = Field(ge=0, le=3, strict=True)
    cluster: Literal["devnet"]
    issued_at: int = Field(strict=True)
    nonce: str = Field(pattern=r"^[a-f0-9]{32}$")
    signature: str = Field(min_length=64, max_length=128)

    def signing_message(self) -> str:
        return (
            "SolBreach certificate mint authorization v1\n"
            f"Wallet: {self.player}\nLevel: {self.level}\nCluster: devnet\n"
            f"Issued at: {self.issued_at}\nNonce: {self.nonce}"
        )
