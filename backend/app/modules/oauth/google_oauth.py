"""
Google OAuth 2.0 Manager for Gmail IMAP access using XOAUTH2.

This module handles:
1. Generating authorization URLs for Google OAuth consent
2. Exchanging authorization codes for access/refresh tokens
3. Refreshing expired access tokens
4. Generating XOAUTH2 authentication strings for IMAP
"""

import os
import logging
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# Google OAuth 2.0 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Scopes for Gmail IMAP access
GMAIL_IMAP_SCOPE = "https://mail.google.com/"
OPENID_SCOPES = "openid email profile"


class GoogleOAuthManager:
    """
    Manages Google OAuth 2.0 flow for Gmail IMAP XOAUTH2 authentication.
    """
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ):
        """
        Initialize the OAuth manager with Google credentials.
        
        Args:
            client_id: Google OAuth Client ID (from env if not provided)
            client_secret: Google OAuth Client Secret (from env if not provided)
            redirect_uri: Callback URL for OAuth flow (from env if not provided)
        """
        self.client_id = client_id or os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.getenv(
            "GOOGLE_OAUTH_REDIRECT_URI",
            "http://localhost:8000/email-configs/oauth/google/callback"
        )
        
        if not self.client_id or not self.client_secret:
            logger.warning("Google OAuth credentials not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET env vars.")
    
    def is_configured(self) -> bool:
        """Check if OAuth credentials are properly configured."""
        return bool(self.client_id and self.client_secret)
    
    def get_redirect_uri(self, request_host: Optional[str] = None) -> str:
        """
        Get the appropriate redirect URI based on the request host.
        This allows the same backend to work in both local and production environments.
        
        Args:
            request_host: The Host header from the request (e.g., 'localhost:4200', 'app.cuenly.com')
            
        Returns:
            The appropriate redirect URI for this environment
        """
        if request_host:
            # Determine protocol based on host
            if 'localhost' in request_host or '127.0.0.1' in request_host:
                protocol = 'http'
            else:
                protocol = 'https'
            
            return f"{protocol}://{request_host}/email-configs/oauth/google/callback"
        
        # Fallback to configured redirect_uri
        return self.redirect_uri
    
    def generate_auth_url(self, state: str, login_hint: Optional[str] = None, redirect_uri: Optional[str] = None) -> str:
        """
        Generate the Google OAuth authorization URL.
        
        Args:
            state: State parameter for CSRF protection (encode user info here)
            login_hint: Optional email to pre-fill in Google sign-in
            
        Returns:
            Authorization URL to redirect the user to
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "response_type": "code",
            "scope": f"{GMAIL_IMAP_SCOPE} {OPENID_SCOPES}",
            "access_type": "offline",  # Required for refresh_token
            "prompt": "consent",  # Force consent to get refresh_token
            "state": state,
        }
        
        if login_hint:
            params["login_hint"] = login_hint
        
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchange the authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from Google callback
            redirect_uri: The redirect URI used in the authorization request
            
        Returns:
            Dict with access_token, refresh_token, expires_in, token_type
            
        Raises:
            Exception: If token exchange fails
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri or self.redirect_uri,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=data)
            
            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"Token exchange failed: {error_data}")
                raise Exception(f"Failed to exchange code: {error_data.get('error_description', error_data.get('error', 'Unknown error'))}")
            
            tokens = response.json()
            logger.info("Successfully exchanged authorization code for tokens")
            return tokens
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token using the refresh token.
        
        Args:
            refresh_token: The stored refresh token
            
        Returns:
            Dict with new access_token and expires_in
            
        Raises:
            Exception: If refresh fails
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=data)
            
            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"Token refresh failed: {error_data}")
                raise Exception(f"Failed to refresh token: {error_data.get('error_description', error_data.get('error', 'Unknown error'))}")
            
            tokens = response.json()
            logger.info("Successfully refreshed access token")
            return tokens
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user info from Google using the access token.
        
        Args:
            access_token: Valid access token
            
        Returns:
            Dict with user info (email, name, etc.)
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code != 200:
                raise Exception("Failed to get user info")
            
            return response.json()
    
    def calculate_token_expiry(self, expires_in: int) -> datetime:
        """
        Calculate the token expiry datetime.
        
        Args:
            expires_in: Seconds until token expires (usually 3600)
            
        Returns:
            Datetime when the token will expire
        """
        # Subtract 5 minutes for safety margin
        return datetime.utcnow() + timedelta(seconds=expires_in - 300)
    
    def is_token_expired(self, token_expiry: Optional[datetime]) -> bool:
        """
        Check if a token is expired or about to expire.
        
        Args:
            token_expiry: The stored expiry datetime
            
        Returns:
            True if token is expired or will expire in less than 5 minutes
        """
        if not token_expiry:
            return True
        return datetime.utcnow() >= token_expiry
    
    @staticmethod
    def generate_xoauth2_string(username: str, access_token: str) -> str:
        """
        Generate the XOAUTH2 authentication string for IMAP.
        
        The format is: user=<email>\\x01auth=Bearer <token>\\x01\\x01
        Then base64 encoded.
        
        Args:
            username: The Gmail address
            access_token: Valid OAuth2 access token
            
        Returns:
            Base64-encoded XOAUTH2 string
        """
        auth_string = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(auth_string.encode()).decode()
    
    @staticmethod
    def get_xoauth2_bytes(username: str, access_token: str) -> bytes:
        """
        Get the raw XOAUTH2 bytes for IMAP authentication.
        
        This is used with imaplib.authenticate() which expects a callable
        that returns the raw bytes (not base64 encoded).
        
        Args:
            username: The Gmail address
            access_token: Valid OAuth2 access token
            
        Returns:
            Raw bytes for XOAUTH2 authentication
        """
        auth_string = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
        return auth_string.encode()

    def refresh_access_token_sync(self, refresh_token: str) -> Dict[str, Any]:
        """
        Synchronous version of refresh_access_token for use in background jobs.
        
        Args:
            refresh_token: The stored refresh token
            
        Returns:
            Dict with new access_token and expires_in
            
        Raises:
            Exception: If refresh fails
        """
        import requests
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        
        try:
            response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=30)
            
            if response.status_code != 200:
                error_data = response.json()
                logger.error(f"Token refresh failed (sync): {error_data}")
                raise Exception(f"Failed to refresh token: {error_data.get('error_description', error_data.get('error', 'Unknown error'))}")
            
            tokens = response.json()
            logger.info("Successfully refreshed access token (sync)")
            return tokens
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during token refresh: {e}")
            raise Exception(f"Network error refreshing token: {str(e)}")


# Singleton instance
_oauth_manager: Optional[GoogleOAuthManager] = None


def get_google_oauth_manager() -> GoogleOAuthManager:
    """Get or create the singleton OAuth manager instance."""
    global _oauth_manager
    if _oauth_manager is None:
        _oauth_manager = GoogleOAuthManager()
    return _oauth_manager
