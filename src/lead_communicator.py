import logging
import httpx
from web3 import Web3
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OutreachEngine")

class RecoveryOutreachEngine:
    def __init__(self, eth_rpc_url: str, postmark_server_token: str):
        self.w3 = Web3(Web3.HTTPProvider(eth_rpc_url))
        self.email_token = postmark_server_token
        self.email_api_url = "https://api.postmarkapp.com/email"

    def reverse_ens_lookup(self, wallet_address: str) -> str:
        """
        Performs a reverse-lookup on an EVM wallet address to locate 
        a registered ENS domain (e.g., alex.eth).
        """
        try:
            checksum_address = self.w3.to_checksum_address(wallet_address)
            # Query the core ENS registry smart contract via standard Web3 methods
            domain_name = self.w3.ens.name(checksum_address)
            if domain_name:
                logger.info(f"ENS Identity Match Found: {wallet_address} -> {domain_name}")
                return domain_name
            return None
        except Exception as e:
            logger.error(f"ENS Reverse Resolution Failed: {str(e)}")
            return None

    async def send_recovery_proposal(self, target_email: str, owner_name: str, asset_summary: str) -> bool:
        """
        Dispatches a structured client outreach communication via verified transactional email.
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": self.email_token
        }
        
        # Professional, non-spam corporate template layout
        email_body = (
            f"Hello {owner_name or 'Asset Owner'},\n\n"
            f"Our institutional asset recovery platform has identified dormant balances or unclaimed assets "
            f"associated with your entity footprint.\n\n"
            f"Asset Details: {asset_summary}\n\n"
            f"If you require assistance securely verifying and executing a claims transfer back to your primary accounts, "
            f"please reply directly to this communication to connect with an estate management consultant.\n\n"
            f"Best regards,\nLegacy Asset Recovery Operations"
        )

        payload = {
            "From": "consulting@yourrecoveryfirm.com",
            "To": target_email,
            "Subject": "Secure Asset Recovery Notification - Action Required",
            "TextBody": email_body,
            "MessageStream": "outbound"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.email_api_url, json=payload, headers=headers, timeout=8.0)
                if response.status_code == 200:
                    logger.info(f"Outreach successfully routed to {target_email}")
                    return True
                logger.error(f"Email gateway rejected payload: {response.text}")
                return False
            except Exception as e:
                logger.critical(f"Critical communication gateway failure: {str(e)}")
                return False
