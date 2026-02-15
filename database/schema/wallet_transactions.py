"""
MongoDB service for storing wallet transactions.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import secrets
import os
import sys

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.logger_config import get_logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__)

from motor.motor_asyncio import AsyncIOMotorDatabase
from database.async_connection import get_async_database


class WalletTransactionsService:
    """Service for MongoDB wallet transactions operations."""
    
    def __init__(self):
        self._db: Optional[AsyncIOMotorDatabase] = None
    
    async def _get_db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = await get_async_database()
        return self._db
    
    def generate_transaction_id(self) -> str:
        """Generate a transaction ID following the schema pattern: txn_[hex]"""
        return f"txn_{secrets.token_hex(8)}"
    
    async def create_transaction(
        self,
        user_id: str,
        transaction_type: str,
        amount: float,
        balance_before: float,
        balance_after: float,
        currency: str = "USD",
        status: str = "pending",
        related_to: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Create a new wallet transaction.
        
        Args:
            user_id: User identifier (must match pattern: user_[alphanumeric_underscore])
            transaction_type: Transaction type (debit, credit, refund)
            amount: Transaction amount (positive value)
            balance_before: Balance before transaction
            balance_after: Balance after transaction
            currency: Currency code (USD, INR)
            status: Transaction status (pending, completed, failed, reversed)
            related_to: Related entity object (type, id, agentId, conversationId)
            description: Transaction description (max 500 chars)
            timestamp: Transaction timestamp (defaults to now)
            
        Returns:
            Transaction ID if successful, None otherwise
        """
        try:
            db = await self._get_db()
            transaction_id = self.generate_transaction_id()
            now = datetime.now(timezone.utc)
            
            transaction_doc = {
                "_id": transaction_id,
                "userId": user_id,
                "transactionType": transaction_type,
                "amount": float(amount),
                "currency": currency,
                "balanceBefore": float(balance_before),
                "balanceAfter": float(balance_after),
                "status": status,
                "timestamp": timestamp or now,
                "createdAt": now
            }
            
            # Add optional fields
            if related_to:
                transaction_doc["relatedTo"] = related_to
            
            if description:
                transaction_doc["description"] = description[:500]  # Enforce max length
            
            # Insert into wallet_transactions collection
            result = await db.wallet_transactions.insert_one(transaction_doc)
            
            if result.inserted_id:
                logger.info(f"✓ Created wallet transaction: {transaction_id} (user: {user_id}, type: {transaction_type}, amount: {amount})")
                return transaction_id
            else:
                logger.error(f"Failed to create wallet transaction: {transaction_id}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error creating wallet transaction: {e}", exc_info=True)
            return None
    
    async def update_transaction_status(
        self,
        transaction_id: str,
        status: str
    ) -> bool:
        """
        Update the status of a transaction.
        
        Args:
            transaction_id: Transaction identifier
            status: New status (pending, completed, failed, reversed)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            db = await self._get_db()
            result = await db.wallet_transactions.update_one(
                {"_id": transaction_id},
                {"$set": {"status": status}}
            )
            
            if result.modified_count > 0:
                logger.info(f"✓ Updated transaction status: {transaction_id} -> {status}")
                return True
            else:
                logger.warning(f"No transaction found to update: {transaction_id}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error updating transaction status: {e}", exc_info=True)
            return False
    
    async def get_transaction(
        self,
        transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a transaction by ID.
        
        Args:
            transaction_id: Transaction identifier
            
        Returns:
            Transaction document if found, None otherwise
        """
        try:
            db = await self._get_db()
            transaction = await db.wallet_transactions.find_one({"_id": transaction_id})
            if transaction:
                logger.debug(f"Retrieved transaction: {transaction_id}")
            else:
                logger.debug(f"Transaction not found: {transaction_id}")
            return transaction
        except Exception as e:
            logger.error(f"Unexpected error retrieving transaction: {e}", exc_info=True)
            return None
    
    async def get_user_transactions(
        self,
        user_id: str,
        status: Optional[str] = None,
        transaction_type: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> list:
        """
        Get transactions for a user, ordered by timestamp.
        
        Args:
            user_id: User identifier
            status: Filter by status (optional)
            transaction_type: Filter by transaction type (optional)
            limit: Maximum number of transactions to return
            skip: Number of transactions to skip
            
        Returns:
            List of transaction documents
        """
        try:
            db = await self._get_db()
            query = {"userId": user_id}
            if status:
                query["status"] = status
            if transaction_type:
                query["transactionType"] = transaction_type
            
            cursor = (
                db.wallet_transactions.find(query)
                .sort("timestamp", -1)
                .skip(skip)
                .limit(limit)
            )
            transactions = await cursor.to_list(length=limit)
            logger.debug(f"Retrieved {len(transactions)} transactions for user: {user_id}")
            return transactions
        except Exception as e:
            logger.error(f"Unexpected error retrieving user transactions: {e}", exc_info=True)
            return []
    
    async def get_transactions_by_related(
        self,
        related_type: Optional[str] = None,
        related_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> list:
        """
        Get transactions by related entity.
        
        Args:
            related_type: Related entity type (agent_launch, message, recharge, refund)
            related_id: Related entity ID
            limit: Maximum number of transactions to return
            skip: Number of transactions to skip
            
        Returns:
            List of transaction documents
        """
        try:
            db = await self._get_db()
            query = {}
            if related_type:
                query["relatedTo.type"] = related_type
            if related_id:
                query["relatedTo.id"] = related_id
            
            if not query:
                logger.warning("At least one of related_type or related_id must be provided")
                return []
            
            cursor = (
                db.wallet_transactions.find(query)
                .sort("timestamp", -1)
                .skip(skip)
                .limit(limit)
            )
            transactions = await cursor.to_list(length=limit)
            logger.debug(f"Retrieved {len(transactions)} transactions by related entity")
            return transactions
        except Exception as e:
            logger.error(f"Unexpected error retrieving transactions by related: {e}", exc_info=True)
            return []
    
    async def reverse_transaction(
        self,
        transaction_id: str,
        reversal_description: Optional[str] = None
    ) -> Optional[str]:
        """
        Reverse a transaction by creating a new reversal transaction.
        
        Args:
            transaction_id: Original transaction ID to reverse
            reversal_description: Description for the reversal transaction
            
        Returns:
            New reversal transaction ID if successful, None otherwise
        """
        try:
            # Get the original transaction
            original = await self.get_transaction(transaction_id)
            if not original:
                logger.error(f"Original transaction not found: {transaction_id}")
                return None
            
            # Create reversal transaction
            reversal_id = await self.create_transaction(
                user_id=original["userId"],
                transaction_type="refund",
                amount=original["amount"],
                balance_before=original["balanceAfter"],
                balance_after=original["balanceBefore"],
                currency=original.get("currency", "USD"),
                status="completed",
                related_to={
                    "type": "refund",
                    "id": transaction_id
                },
                description=reversal_description or f"Reversal of transaction {transaction_id}"
            )
            
            if reversal_id:
                # Update original transaction status
                await self.update_transaction_status(transaction_id, "reversed")
                logger.info(f"✓ Reversed transaction: {transaction_id} -> {reversal_id}")
            
            return reversal_id
                
        except Exception as e:
            logger.error(f"Unexpected error reversing transaction: {e}", exc_info=True)
            return None


# Global instance (singleton pattern)
_wallet_transactions_service: Optional[WalletTransactionsService] = None


def get_wallet_transactions_service() -> WalletTransactionsService:
    """Get or create Wallet Transactions service instance."""
    global _wallet_transactions_service
    if _wallet_transactions_service is None:
        _wallet_transactions_service = WalletTransactionsService()
    return _wallet_transactions_service


if __name__ == "__main__":
    """Test the wallet transactions service and create collection."""
    print("=" * 60)
    print("Testing Wallet Transactions Service")
    print("=" * 60)
    
    try:
        # Initialize service (this will connect to MongoDB)
        service = get_wallet_transactions_service()
        print("✓ Connected to MongoDB")
        
        # Test creating a transaction (this will create the collection)
        test_user_id = "user_test_123"
        txn_id = service.create_transaction(
            user_id=test_user_id,
            transaction_type="credit",
            amount=100.0,
            balance_before=0.0,
            balance_after=100.0,
            currency="USD",
            status="completed",
            description="Test transaction"
        )
        
        if txn_id:
            print(f"✓ Created test transaction: {txn_id}")
            print(f"✓ Collection 'wallet_transactions' is now created")
            
            # Clean up test transaction
            result = service.db.wallet_transactions.delete_one({"_id": txn_id})
            if result.deleted_count > 0:
                print(f"✓ Cleaned up test transaction")
        else:
            print("✗ Failed to create test transaction")
        
        # Close connection
        service.close()
        print("\n✓ Test completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)

