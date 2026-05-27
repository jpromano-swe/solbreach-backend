from app.core.config.settings import get_settings
from app.shared.blockchain import BlockchainClientInterface, SolanaDevnetAdapter


def get_blockchain_client() -> BlockchainClientInterface:
    return SolanaDevnetAdapter(get_settings().solana_devnet_rpc_url)
