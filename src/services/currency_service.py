"""
Currency Service
Detects user location and determines currency (INR for India, USD for others).
Uses loginLocation as primary source, with fallback to country/timezone.
"""
import os
import sys
# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from utils.logger_config import get_logger
from typing import Optional

# Initialize logger
logger = get_logger(__name__)


class CurrencyService:
    """Service for currency detection and formatting based on user location"""
    
    @staticmethod
    def detect_currency(login_location: Optional[str] = None, country: Optional[str] = None, timezone: Optional[str] = None) -> str:
        """
        Detect currency based on login location, country code, or timezone.
        
        Priority order:
        1. loginLocation (primary) - "India" -> INR, others -> USD
        2. country code (fallback) - "IN"/"IND"/"INDIA" -> INR, others -> USD
        3. timezone (fallback) - India timezones -> INR, others -> USD
        4. Default to USD if none provided
        
        Args:
            login_location: User's login location (e.g., "India", "US", "Other") - optional
            country: Country code (e.g., "IN", "US") - optional, used as fallback
            timezone: User timezone (e.g., "Asia/Kolkata") - optional, used as fallback
            
        Returns:
            Currency code: "INR" for India, "USD" for others
        """
        # Priority 1: Use loginLocation if provided (primary source)
        if login_location:
            login_location_upper = login_location.upper().strip()
            # Check for India (case-insensitive)
            if login_location_upper in ["INDIA", "IN", "IND"]:
                logger.debug(f"Currency detected from loginLocation: INR (loginLocation: {login_location})")
                return "INR"
            else:
                # All other locations use USD (US, UK, CA, AU, Other, etc.)
                logger.debug(f"Currency detected from loginLocation: USD (loginLocation: {login_location})")
                return "USD"
        
        # Priority 2: Use country code if provided (fallback)
        if country:
            country_upper = country.upper().strip()
            # India country codes
            if country_upper in ["IN", "IND", "INDIA"]:
                logger.debug(f"Currency detected from country code: INR (country: {country})")
                return "INR"
            else:
                # All other countries use USD (US, UK, CA, AU, etc.)
                logger.debug(f"Currency detected from country code: USD (country: {country})")
                return "USD"
        
        # Priority 3: Derive from timezone (fallback)
        if timezone:
            timezone_lower = timezone.lower()
            india_timezones = ["asia/kolkata", "asia/calcutta", "ist", "india"]
            
            if any(tz in timezone_lower for tz in india_timezones):
                logger.debug(f"Currency detected from timezone: INR (timezone: {timezone})")
                return "INR"
            else:
                logger.debug(f"Currency detected from timezone: USD (timezone: {timezone})")
                return "USD"
        
        # Default: Use USD when no location information is provided
        logger.debug("No location information provided, defaulting to USD")
        return "USD"
    
    @staticmethod
    def get_currency_symbol(currency: str) -> str:
        """
        Get currency symbol for display.
        
        Args:
            currency: Currency code ("INR" or "USD")
            
        Returns:
            Currency symbol ("₹" or "$")
        """
        if currency == "INR":
            return "₹"
        elif currency == "USD":
            return "$"
        else:
            logger.warning(f"Unknown currency: {currency}, defaulting to ₹")
            return "₹"
    
    @staticmethod
    def format_currency(amount: float, currency: str) -> str:
        """
        Format amount with currency symbol.
        
        Args:
            amount: Amount to format
            currency: Currency code ("INR" or "USD")
            
        Returns:
            Formatted string (e.g., "₹30" or "$0.40")
        """
        symbol = CurrencyService.get_currency_symbol(currency)
        
        if currency == "USD":
            # USD: Show 2 decimal places
            return f"{symbol}{amount:.2f}"
        else:  # INR
            # INR: Show no decimal places (whole numbers)
            return f"{symbol}{int(amount)}"

