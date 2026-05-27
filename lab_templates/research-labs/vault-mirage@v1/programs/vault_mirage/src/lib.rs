pub const ORACLE_SCALE: u64 = 100;
pub const MIN_HEALTH_FACTOR: u64 = 1_000;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCode {
    InsufficientHealth,
    MathOverflow,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct Vault {
    pub total_deposits: u64,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct UserPosition {
    pub deposits: u64,
}

pub fn deposit(
    vault: &mut Vault,
    user: &mut UserPosition,
    amount: u64,
    oracle_price: u64,
) -> Result<(), ErrorCode> {
    // Vulnerable: multiplication can overflow before scaling.
    let collateral_value = amount * oracle_price / ORACLE_SCALE;

    if collateral_value < MIN_HEALTH_FACTOR {
        return Err(ErrorCode::InsufficientHealth);
    }

    vault.total_deposits = vault
        .total_deposits
        .checked_add(amount)
        .ok_or(ErrorCode::MathOverflow)?;

    user.deposits = user
        .deposits
        .checked_add(amount)
        .ok_or(ErrorCode::MathOverflow)?;

    Ok(())
}
