from pydantic import BaseModel, EmailStr, Field

from app.modules.users.presentation.schemas.user import UserResponse


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class WalletNonceRequest(BaseModel):
    wallet_address: str = Field(min_length=32, max_length=64)


class WalletNonceResponse(BaseModel):
    wallet_address: str
    nonce: str
    message: str
    expires_at: str


class WalletVerifyRequest(BaseModel):
    wallet_address: str = Field(min_length=32, max_length=64)
    nonce: str = Field(min_length=16, max_length=128)
    signature: str = Field(min_length=64, max_length=256)
