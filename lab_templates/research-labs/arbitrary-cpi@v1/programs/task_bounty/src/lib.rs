use anchor_lang::prelude::*;

declare_id!("TaskBnty1111111111111111111111111111111111");

#[program]
pub mod task_bounty {
    use super::*;

    pub fn create_task(_ctx: Context<CreateTask>) -> Result<()> {
        Ok(())
    }

    pub fn fund_task(_ctx: Context<FundTask>) -> Result<()> {
        Ok(())
    }

    pub fn delegate_payout(_ctx: Context<DelegatePayout>) -> Result<()> {
        Ok(())
    }

    pub fn execute_delegated_payout(_ctx: Context<ExecuteDelegatedPayout>) -> Result<()> {
        // Vulnerability model: the delegated payout flow trusts a caller-supplied CPI target.
        // The SolBreach runtime executes a deterministic session-scoped model of this behavior.
        Ok(())
    }
}

#[derive(Accounts)]
pub struct CreateTask {}

#[derive(Accounts)]
pub struct FundTask {}

#[derive(Accounts)]
pub struct DelegatePayout {}

#[derive(Accounts)]
pub struct ExecuteDelegatedPayout {}
