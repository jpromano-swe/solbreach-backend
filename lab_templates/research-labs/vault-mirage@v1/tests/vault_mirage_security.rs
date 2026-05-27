use vault_mirage_lab::{deposit, ErrorCode, UserPosition, Vault};

#[test]
fn normal_deposit_accepts_normal_oracle_input() {
    let mut vault = Vault::default();
    let mut user = UserPosition::default();

    let result = deposit(&mut vault, &mut user, 1_000, 200);

    assert_eq!(result, Ok(()));
    assert_eq!(vault.total_deposits, 1_000);
    assert_eq!(user.deposits, 1_000);
}

#[test]
fn overflow_shaped_oracle_input_is_rejected() {
    let mut vault = Vault::default();
    let mut user = UserPosition::default();

    let result = deposit(&mut vault, &mut user, u64::MAX, 2);

    assert_eq!(result, Err(ErrorCode::MathOverflow));
    assert_eq!(vault.total_deposits, 0);
    assert_eq!(user.deposits, 0);
}
