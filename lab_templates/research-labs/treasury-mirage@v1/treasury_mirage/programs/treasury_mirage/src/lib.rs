use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};

declare_id!("Mirage1111111111111111111111111111111111111");

#[program]
pub mod treasury_mirage {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let position = &mut ctx.accounts.position;
        position.owner = ctx.accounts.user.key();
        position.credited_collateral = 0;
        Ok(())
    }

    pub fn deposit_collateral(ctx: Context<DepositCollateral>, amount: u64) -> Result<()> {
        // VULNERABILITY: Missing Mint Validation
        // The program blindly transfers from the provided collateral_account
        // to the vault_account without verifying that the collateral_account's mint
        // is the accepted one. An attacker can pass a counterfeit token account.
        
        let cpi_accounts = Transfer {
            from: ctx.accounts.collateral_account.to_account_info(),
            to: ctx.accounts.vault_account.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, amount)?;

        // Credit the attacker's position based on the deposited amount
        let position = &mut ctx.accounts.position;
        position.credited_collateral = position.credited_collateral.checked_add(amount).unwrap();

        Ok(())
    }

    pub fn withdraw_against_credit(ctx: Context<WithdrawAgainstCredit>, amount: u64) -> Result<()> {
        let position = &mut ctx.accounts.position;
        
        if position.credited_collateral < amount {
            return err!(VaultError::InsufficientCredit);
        }

        // Subtract credit
        position.credited_collateral = position.credited_collateral.checked_sub(amount).unwrap();

        // Withdraw legitimate treasury value (in SOL for simplicity, to match the spike requirement
        // "withdraw legitimate treasury value against that invalid credit" and the brief's lamports)
        let treasury = &mut ctx.accounts.treasury;
        let reward_account = &mut ctx.accounts.reward_account;

        if treasury.lamports() < amount {
            return err!(VaultError::InsufficientTreasury);
        }

        treasury.sub_lamports(amount)?;
        reward_account.add_lamports(amount)?;

        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = user,
        space = 8 + 32 + 8,
        seeds = [b"position", user.key().as_ref()],
        bump
    )]
    pub position: Account<'info, Position>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct DepositCollateral<'info> {
    #[account(mut, constraint = position.owner == user.key())]
    pub position: Account<'info, Position>,
    
    // Attacker provides this
    #[account(mut)]
    pub collateral_account: Account<'info, TokenAccount>,
    
    #[account(mut)]
    pub vault_account: Account<'info, TokenAccount>,
    
    #[account(mut)]
    pub user: Signer<'info>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct WithdrawAgainstCredit<'info> {
    #[account(mut, constraint = position.owner == user.key())]
    pub position: Account<'info, Position>,
    
    /// CHECK: The treasury is just a PDA that holds SOL
    #[account(mut, seeds = [b"treasury"], bump)]
    pub treasury: AccountInfo<'info>,
    
    /// CHECK: Attacker's reward account
    #[account(mut)]
    pub reward_account: AccountInfo<'info>,
    
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct Position {
    pub owner: Pubkey,
    pub credited_collateral: u64,
}

#[error_code]
pub enum VaultError {
    #[msg("Insufficient position credit")]
    InsufficientCredit,
    #[msg("Insufficient treasury balance")]
    InsufficientTreasury,
}
