"""
Wallet Microservice Client
Fetches wallet balance from external microservice
"""
import os
from typing import Optional
import httpx
from dotenv import load_dotenv
import os
import sys
# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from utils.logger_config import get_logger

load_dotenv()

# Initialize logger
logger = get_logger(__name__)


class WalletMicroserviceClient:
    """Client for interacting with wallet microservice"""
    
    def __init__(self):
        logger.info("Initializing WalletMicroserviceClient")
        # In production, this would be the actual microservice URL
        # For now, using hardcoded values or environment variable
        self.base_url = os.getenv("WALLET_SERVICE_URL", "http://wallet-service:8001")
        self.timeout = 5.0  # 5 second timeout
        logger.info(f"Wallet service configured - base_url: {self.base_url}, timeout: {self.timeout}s")
    
    async def get_balance(self, user_id: str) -> float:
        """
        Fetch wallet balance for a user from microservice
        
        Args:
            user_id: User identifier
            
        Returns:
            Wallet balance as float
            
        Note: This is a mock implementation. Replace with actual microservice call.
        """
        logger.info(f"Fetching wallet balance for user: {user_id}")
        # TODO: Replace with actual microservice HTTP call
        # Example implementation:
        # async with httpx.AsyncClient(timeout=self.timeout) as client:
        #     response = await client.get(
        #         f"{self.base_url}/api/wallet/balance",
        #         params={"userId": user_id}
        #     )
        #     response.raise_for_status()
        #     data = response.json()
        #     return float(data["balance"])
        
        # Mock implementation - hardcoded for now
        # In production, this would make an actual HTTP call
        mock_balances = {
            "user_789": 245.0,
            "default": 100.0
        }
        
        balance = mock_balances.get(user_id, mock_balances["default"])
        logger.info(f"Wallet balance for user {user_id}: {balance}")
        return balance
    
    async def deduct_balance(self, user_id: str, amount: float) -> bool:
        """
        Deduct balance from user's wallet
        
        Args:
            user_id: User identifier
            amount: Amount to deduct
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Deducting {amount} from wallet for user: {user_id}")
        # TODO: Implement actual microservice call
        # This would be called when user actually launches an agent
        logger.info(f"Balance deduction successful for user: {user_id}")
        return True
    
    async def check_sufficient_balance(self, user_id: str, required_amount: float):
        """
        Check if user has sufficient balance
        
        Args:
            user_id: User identifier
            required_amount: Required amount
            
        Returns:
            Tuple of (has_sufficient_balance, current_balance)
        """
        logger.debug(f"Checking sufficient balance for user: {user_id}, required: {required_amount}")
        current_balance = await self.get_balance(user_id)
        has_sufficient = current_balance >= required_amount
        logger.info(f"Balance check for user {user_id} - required: {required_amount}, current: {current_balance}, sufficient: {has_sufficient}")
        return has_sufficient, current_balance

