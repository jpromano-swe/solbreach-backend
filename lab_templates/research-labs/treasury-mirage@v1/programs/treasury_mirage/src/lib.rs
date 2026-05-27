pub const ACCEPTED_COLLATERAL_MINT: &str = "accepted_collateral_mint";

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TokenAccount {
    pub mint: String,
    pub owner: String,
    pub amount: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Position {
    pub owner: String,
    pub credited_collateral: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TreasuryVault {
    pub lamports: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum VaultError {
    InsufficientCredit,
    InsufficientTreasury,
}

// Vulnerable: this function trusts the caller-supplied collateral account amount
// without proving that the token account mint equals ACCEPTED_COLLATERAL_MINT.
pub fn deposit_collateral(position: &mut Position, collateral: &TokenAccount) {
    position.credited_collateral = position
        .credited_collateral
        .saturating_add(collateral.amount);
}

pub fn withdraw_against_credit(
    position: &Position,
    treasury: &mut TreasuryVault,
    reward_lamports: &mut u64,
    amount: u64,
) -> Result<(), VaultError> {
    if position.credited_collateral < amount {
        return Err(VaultError::InsufficientCredit);
    }
    if treasury.lamports < amount {
        return Err(VaultError::InsufficientTreasury);
    }
    treasury.lamports -= amount;
    *reward_lamports = reward_lamports.saturating_add(amount);
    Ok(())
}
