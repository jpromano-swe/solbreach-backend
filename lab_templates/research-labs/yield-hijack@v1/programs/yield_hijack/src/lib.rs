use anchor_lang::prelude::*;

declare_id!("Yield11111111111111111111111111111111111111");

#[program]
pub mod yield_hijack {
    use super::*;

    pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
        require!(amount > 0, StakingError::InvalidAmount);

        let position = &mut ctx.accounts.position;
        if position.pool == Pubkey::default() {
            position.pool = ctx.accounts.pool.key();
        }

        // Vulnerability: this position PDA is scoped only to the pool.
        // A later staker in the same pool overwrites ownership of the same position.
        position.owner = ctx.accounts.user.key();
        position.staked_amount = position
            .staked_amount
            .checked_add(amount)
            .ok_or(StakingError::Overflow)?;

        // Existing pending rewards intentionally remain attached to the shared position.
        Ok(())
    }

    pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()> {
        let position = &mut ctx.accounts.position;
        require_keys_eq!(
            position.owner,
            ctx.accounts.user.key(),
            StakingError::InvalidPositionOwner
        );
        require!(position.pending_rewards > 0, StakingError::NoRewardsAvailable);

        position.pending_rewards = 0;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Stake<'info> {
    pub user: Signer<'info>,
    pub pool: Account<'info, PoolConfig>,
    #[account(
        mut,
        seeds = [b"stake_position", pool.key().as_ref()],
        bump
    )]
    pub position: Account<'info, StakePosition>,
}

#[derive(Accounts)]
pub struct ClaimRewards<'info> {
    pub user: Signer<'info>,
    pub pool: Account<'info, PoolConfig>,
    #[account(
        mut,
        seeds = [b"stake_position", pool.key().as_ref()],
        bump
    )]
    pub position: Account<'info, StakePosition>,
}

#[account]
#[derive(InitSpace)]
pub struct PoolConfig {
    pub authority: Pubkey,
    pub stake_mint: Pubkey,
    pub reward_mint: Pubkey,
    pub stake_vault: Pubkey,
    pub reward_vault: Pubkey,
    pub advertised_apy_bps: u64,
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct StakePosition {
    pub owner: Pubkey,
    pub pool: Pubkey,
    pub staked_amount: u64,
    pub pending_rewards: u64,
    pub bump: u8,
}

#[error_code]
pub enum StakingError {
    #[msg("Amount must be greater than zero.")]
    InvalidAmount,
    #[msg("Position owner does not match signer.")]
    InvalidPositionOwner,
    #[msg("No rewards are available.")]
    NoRewardsAvailable,
    #[msg("Arithmetic overflow.")]
    Overflow,
}
