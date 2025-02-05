"""Models for the Dex-Trade API client."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderType(Enum):
    """Order types for trading."""
    BUY = 0
    SELL = 1


class TradeType(Enum):
    """Types of trades available."""
    LIMIT = 0
    MARKET = 1
    STOP_LIMIT = 2
    QUICK_MARKET = 3
    HIDDEN_LIMIT = 4


class OrderStatus(Enum):
    """Possible statuses for orders."""
    IN_PROCESS = 0
    ADDED_TO_BOOK = 1
    FILLED_FULL = 2
    CLOSED_PARTIAL_FILLED = 3


@dataclass
class DexTradeConfig:
    """Configuration for DexTrade API client.

    Attributes:
        base_url: Base URL for REST API endpoints
        socket_url: URL for WebSocket connections
        login_token: Authentication token for private API calls
        secret: Secret key for request signing
    """
    base_url: str = "https://api.dex-trade.com/v1"
    socket_url: str = "https://socket.dex-trade.com"
    login_token: Optional[str] = None
    secret: Optional[str] = None


class ValidationError(Exception):
    """Raised when request parameters are invalid."""
    pass


class AuthenticationError(Exception):
    """Raised when API authentication fails."""
    pass


class RateLimitError(Exception):
    """Raised when API rate limits are exceeded."""
    pass
