import logging
import asyncio
import random
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from web3 import Web3
from web3.exceptions import Web3RPCError
import httpx

# Configure robust, production-ready logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ResilientOrchestrator")

class FaultTolerantScanner:
    def __init__(self, eth_rpc_url: str):
        """
        Initializes the blockchain interface provider.
        """
        self.w3 = Web3(Web3.HTTPProvider(eth_rpc_url))
        
    # =========================================================================
    # RULE: Automatically retry when the node drops connections or times out
    # =========================================================================
    @retry(
        retry=retry_if_exception_type((Web3RPCError, ConnectionError, TimeoutError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=16),
        reraise=True  # Spills the final error upward if all 5 attempts fail completely
    )
    def fetch_evm_balance_safely(self, checksum_address: str) -> float:
        """
        Queries the EVM RPC node. If a network drop occurs, tenacity intercepts 
        the exception, waits exponentially, and retries.
        """
        logger.info(f"📡 Querying on-chain balance for: {checksum_address}")
        balance_wei = self.w3.eth.get_balance(checksum_address)
        return float(self.w3.from_wei(balance_wei, 'ether'))


class FaultTolerantNotifier:
    def __init__(self, bot_token: str, channel_id: str):
        """
        Initializes the HTTP engine for Telegram notification delivery.
        """
        self.client = httpx.AsyncClient(timeout=10.0)
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.channel_id = channel_id

    # =========================================================================
    # RULE: Handle Telegram API rate-limiting (HTTP 429) or drops asynchronously
    # =========================================================================
    async def dispatch_wallet_update_alert(self, client_name: str, wallet_data: dict) -> bool:
        """
        Formats and dispatches network notifications using an internal retry block 
        to handle dropped sockets or sudden rate limits cleanly.
        """
        text = (
            f"🚨 *High-Value Legacy Asset Discovered*\n\n"
            f"👤 *Owner:* {client_name}\n"
            f"🌐 *Network:* {wallet_data['network']}\n"
            f"💳 *Address:* `{wallet_data['address']}`\n"
            f"💰 *Balance:* {wallet_data['balance']:.4f} ETH\n\n"
            f"⚡ _Pipeline proceeding with identity lookup and outreach mapping..._"
        )

        for attempt in range(1, 6):
            try:
                payload = {
                    "chat_id": self.channel_id, 
                    "text": text, 
                    "parse_mode": "Markdown"
                }
                response = await self.client.post(self.url, json=payload)
                
                # Intercept rate limiting gracefully
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    logger.warning(f"⚠️ Telegram rate limit hit (429). Backing off for {retry_after}s...")
                    await asyncio.sleep(retry_after + random.uniform(0.5, 1.5))  # Added anti-collision Jitter
                    continue
                    
                response.raise_for_status()
                logger.info(f"📢 Notification successfully dispatched to {self.channel_id}.")
                return True
                
            except (httpx.NetworkError, httpx.TimeoutException) as network_error:
                sleep_duration = (2 ** attempt) + random.uniform(0.1, 0.9)  # Exponential backoff + Jitter
                logger.error(f"⏳ Network glitch ({network_error}). Retry {attempt}/5 in {sleep_duration:.2f}s")
                await asyncio.sleep(sleep_duration)
                
        logger.critical("❌ Data Pipeline Warning: Notification dropped permanently after 5 failed attempts.")
        return False
