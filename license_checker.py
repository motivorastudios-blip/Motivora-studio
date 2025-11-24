#!/usr/bin/env python3
"""
License Checker - Validates user licenses via Lemon Squeezy API.
This runs in the desktop app to verify subscription status.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()

# Lemon Squeezy Configuration
LEMON_SQUEEZY_API_URL = "https://api.lemonsqueezy.com/v1"
LEMON_SQUEEZY_API_KEY = os.environ.get("LEMON_SQUEEZY_API_KEY")
LEMON_SQUEEZY_STORE_ID = os.environ.get("LEMON_SQUEEZY_STORE_ID")
LEMON_SQUEEZY_VARIANT_ID_FREE = os.environ.get("LEMON_SQUEEZY_VARIANT_ID_FREE")  # Optional
LEMON_SQUEEZY_VARIANT_ID_PRO = os.environ.get("LEMON_SQUEEZY_VARIANT_ID_PRO")
LEMON_SQUEEZY_VARIANT_ID_ENTERPRISE = os.environ.get("LEMON_SQUEEZY_VARIANT_ID_ENTERPRISE")

# License cache settings
CACHE_DURATION_MINUTES = 60  # Cache license status for 1 hour
CACHE_FILE = Path.home() / ".motivora_license_cache.json"


class LicenseChecker:
    """Validates licenses via Lemon Squeezy API."""
    
    def __init__(self):
        self.api_key = LEMON_SQUEEZY_API_KEY
        self.store_id = LEMON_SQUEEZY_STORE_ID
        self.cache_file = CACHE_FILE
        self.cache_duration = timedelta(minutes=CACHE_DURATION_MINUTES)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        if not self.api_key:
            return {}
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
        }
    
    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Load cached license data."""
        if not self.cache_file.exists():
            return None
        
        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)
                cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
                if datetime.utcnow() - cached_at < self.cache_duration:
                    return data
        except Exception:
            pass
        
        return None
    
    def _save_cache(self, license_key: str, tier: str, expires_at: Optional[datetime] = None):
        """Save license data to cache."""
        try:
            data = {
                "license_key": license_key,
                "tier": tier,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "cached_at": datetime.utcnow().isoformat(),
            }
            with open(self.cache_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass
    
    def validate_license(self, license_key: str, email: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate a license key with Lemon Squeezy.
        
        Returns:
            {
                "valid": bool,
                "tier": str,  # "free", "pro", "enterprise"
                "expires_at": Optional[str],
                "message": str,
            }
        """
        if not license_key:
            return {
                "valid": False,
                "tier": "free",
                "expires_at": None,
                "message": "No license key provided",
            }
        
        # Check cache first
        cache = self._load_cache()
        if cache and cache.get("license_key") == license_key:
            expires_at = None
            if cache.get("expires_at"):
                expires_at = datetime.fromisoformat(cache["expires_at"])
                if expires_at and expires_at < datetime.utcnow():
                    return {
                        "valid": False,
                        "tier": "free",
                        "expires_at": None,
                        "message": "License has expired",
                    }
            
            return {
                "valid": True,
                "tier": cache.get("tier", "free"),
                "expires_at": cache.get("expires_at"),
                "message": "License valid (cached)",
            }
        
        # If no API key configured, allow local development (free tier)
        if not self.api_key:
            return {
                "valid": True,
                "tier": "free",
                "expires_at": None,
                "message": "Development mode - no API key configured",
            }
        
        # Call Lemon Squeezy API
        try:
            # Use Lemon Squeezy License Keys API
            # Note: You'll need to implement based on Lemon Squeezy's actual API
            # This is a simplified version - adjust based on their docs
            
            # For now, we'll check subscriptions by email
            if email:
                subscriptions = self._get_user_subscriptions(email)
                if subscriptions:
                    # Find active subscription
                    for sub in subscriptions:
                        if sub.get("status") == "active":
                            variant_id = sub.get("attributes", {}).get("variant_id")
                            tier = self._variant_to_tier(variant_id)
                            expires_at = sub.get("attributes", {}).get("expires_at")
                            
                            result = {
                                "valid": True,
                                "tier": tier,
                                "expires_at": expires_at,
                                "message": "License valid",
                            }
                            
                            # Cache result
                            exp_dt = None
                            if expires_at:
                                try:
                                    exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                                except Exception:
                                    pass
                            self._save_cache(license_key, tier, exp_dt)
                            
                            return result
            
            # If no active subscription found
            return {
                "valid": False,
                "tier": "free",
                "expires_at": None,
                "message": "No active subscription found",
            }
            
        except Exception as e:
            # On API error, use cache if available (cache loaded earlier)
            cached = self._load_cache()
            if cached and cached.get("license_key") == license_key:
                return {
                    "valid": True,
                    "tier": cached.get("tier", "free"),
                    "expires_at": cached.get("expires_at"),
                    "message": f"License valid (cached) - API error: {str(e)}",
                }
            
            return {
                "valid": False,
                "tier": "free",
                "expires_at": None,
                "message": f"License validation failed: {str(e)}",
            }
    
    def _get_user_subscriptions(self, email: str) -> list:
        """Get user subscriptions from Lemon Squeezy by email."""
        if not self.api_key or not self.store_id:
            return []
        
        try:
            # Get customers by email
            response = requests.get(
                f"{LEMON_SQUEEZY_API_URL}/customers",
                headers=self._get_headers(),
                params={"filter[email]": email},
                timeout=10,
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            customers = data.get("data", [])
            if not customers:
                return []
            
            customer_id = customers[0].get("id")
            
            # Get subscriptions for this customer
            response = requests.get(
                f"{LEMON_SQUEEZY_API_URL}/subscriptions",
                headers=self._get_headers(),
                params={"filter[customer_id]": customer_id},
                timeout=10,
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            return data.get("data", [])
            
        except Exception:
            return []
    
    def _variant_to_tier(self, variant_id: Optional[str]) -> str:
        """Map Lemon Squeezy variant ID to subscription tier."""
        if not variant_id:
            return "free"
        
        if variant_id == LEMON_SQUEEZY_VARIANT_ID_PRO:
            return "pro"
        elif variant_id == LEMON_SQUEEZY_VARIANT_ID_ENTERPRISE:
            return "enterprise"
        else:
            return "free"
    
    def clear_cache(self):
        """Clear license cache."""
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
            except Exception:
                pass


# Global checker instance to avoid creating multiple instances
_checker_instance: Optional[LicenseChecker] = None


def get_checker() -> LicenseChecker:
    """Get or create global license checker instance."""
    global _checker_instance
    if _checker_instance is None:
        _checker_instance = LicenseChecker()
    return _checker_instance


# Convenience function for Flask app
def get_user_tier(license_key: Optional[str] = None, email: Optional[str] = None) -> str:
    """
    Get user's subscription tier.
    Returns: "free", "pro", or "enterprise"
    """
    result = get_checker().validate_license(license_key or "", email)
    return result.get("tier", "free") if result.get("valid") else "free"


def can_download(tier: str) -> bool:
    """Check if tier allows downloads."""
    return tier in ("pro", "enterprise")


def can_render_unlimited(tier: str) -> bool:
    """Check if tier allows unlimited renders."""
    return True  # All tiers can render unlimited, but free gets watermarks


if __name__ == "__main__":
    # Test the license checker
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python license_checker.py <license_key> [email]")
        sys.exit(1)
    
    license_key = sys.argv[1]
    email = sys.argv[2] if len(sys.argv) > 2 else None
    
    checker = LicenseChecker()
    result = checker.validate_license(license_key, email)
    
    print(json.dumps(result, indent=2))


