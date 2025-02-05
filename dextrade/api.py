"""
Dex-Trade API client implementation.

This module provides the main API client for interacting with the Dex-Trade
cryptocurrency exchange, supporting both REST and WebSocket endpoints.
"""

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
from dotenv import load_dotenv

from .models import (
    DexTradeConfig,
    OrderType,
    TradeType,
    ValidationError,
    AuthenticationError,
    RateLimitError,
)
from .websocket import DexTradeWebSocket

logger = logging.getLogger(__name__)


class DexTradeAPI:
    """Python client for the Dex-Trade API."""

    def __init__(self, config: DexTradeConfig):
        """
        Initialize the API client.

        Args:
            config: Configuration object containing API credentials and URLs
        """
        self.config = config
        self.session = requests.Session()
        if config.login_token:
            self.session.headers.update({
                'Content-Type': 'application/json'
            })
        self.ws = DexTradeWebSocket(config.socket_url)

    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> 'DexTradeAPI':
        """
        Create DexTradeAPI instance using credentials from .env file.

        Args:
            env_path: Optional path to .env file. If not provided,
                     looks for .env in current directory

        Returns:
            DexTradeAPI: Configured API client

        Raises:
            ValueError: If required environment variables are missing
        """
        if env_path:
            load_dotenv(env_path)
        else:
            # Look for .env in current directory and parent directories
            env_path = Path('.env')
            if not env_path.exists():
                # Try parent directory if not in current
                env_path = Path('..') / '.env'
            load_dotenv(env_path)

        login_token = os.getenv('DEXTRADE_LOGIN_TOKEN')
        secret = os.getenv('DEXTRADE_SECRET')

        if not login_token or not secret:
            raise ValueError(
                "Missing required environment variables. "
                "Please ensure DEXTRADE_LOGIN_TOKEN and DEXTRADE_SECRET "
                "are set in your .env file"
            )

        config = DexTradeConfig(
            login_token=login_token,
            secret=secret
        )
        return cls(config)

    def _get_signature_string(self, params: Dict[str, Any]) -> str:
        """
        Get the string that will be used to generate the signature.

        Args:
            params: Request parameters to sign

        Returns:
            str: String to be hashed
        """
        sorted_params = dict(sorted(params.items()))
        values = []
        for key, value in sorted_params.items():
            if isinstance(value, dict):
                flattened = dict(sorted(value.items()))
                values.extend(str(v) for v in flattened.values())
            else:
                values.append(str(value))
        return ''.join(values) + self.config.secret

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate signature for private API requests.

        Args:
            params: Request parameters to sign

        Returns:
            str: Generated signature

        Raises:
            ValueError: If secret key is missing
        """
        if not self.config.secret:
            raise ValueError("Secret key is required for private API calls")
        values_str = self._get_signature_string(params)
        return hashlib.sha256(values_str.encode()).hexdigest()

    def _make_request(
            self,
            method: str,
            endpoint: str,
            params: Optional[Dict] = None,
            private: bool = False
    ) -> Dict:
        """
        Make HTTP request to API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Request parameters
            private: Whether this is a private API call requiring authentication

        Returns:
            Dict: API response

        Raises:
            AuthenticationError: If authentication fails
            ValidationError: If request parameters are invalid
            RateLimitError: If rate limit is exceeded
            requests.exceptions.RequestException: For other request errors
        """
        if params is None:
            params = {}

        url = f"{self.config.base_url}{endpoint}"

        if private:
            if not self.config.login_token or not self.config.secret:
                raise ValueError("login_token and secret are required for private API calls")

            if 'request_id' not in params:
                params['request_id'] = str(int(datetime.now().timestamp() * 1000000))

            signature = self._generate_signature(params)

            headers = {
                'Content-Type': 'application/json',
                'login-token': self.config.login_token,
                'x-auth-sign': signature
            }

            try:
                response = requests.post(url, headers=headers, json=params)
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {str(e)}")
                raise

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                error_body = response.json() if response.text else {}
                if response.status_code == 401:
                    raise AuthenticationError("Invalid credentials")
                elif response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded")
                elif response.status_code == 400:
                    raise ValidationError(error_body.get('error', 'Invalid request parameters'))
                raise
        else:
            try:
                if method == 'GET':
                    response = requests.get(url, params=params)
                else:
                    response = requests.post(url, json=params)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {str(e)}")
                raise

        return response.json()

    # Public API Methods
    def get_symbols(self) -> List[Dict]:
        """
        Get list of available trading pairs.

        Returns:
            List[Dict]: List of trading pair information
        """
        response = self._make_request('GET', '/public/symbols')
        return response['data']

    def get_ticker(self, pair: str) -> Dict:
        """
        Get ticker information for a trading pair.

        Args:
            pair: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Dict: Ticker information
        """
        return self._make_request('GET', '/public/ticker', {'pair': pair})

    def get_order_book(self, pair: str) -> Dict:
        """
        Get order book for a trading pair.

        Args:
            pair: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Dict: Order book data
        """
        return self._make_request('GET', '/public/book', {'pair': pair})

    def get_trade_history(self, pair: str) -> List[Dict]:
        """
        Get trade history for a trading pair.

        Args:
            pair: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            List[Dict]: List of recent trades
        """
        return self._make_request('GET', '/public/trades', {'pair': pair})

    def get_candlesticks(
            self,
            pair: str,
            period: str = '60',
            end: Optional[int] = None,
            limit: int = 1000
    ) -> List[Dict]:
        """
        Get candlestick data for a trading pair.

        Args:
            pair: Trading pair symbol (e.g., 'BTCUSDT')
            period: Time period ('60' for 1h, 'D' for 1d, 'W' for 1w)
            end: End timestamp
            limit: Number of candles to return

        Returns:
            List[Dict]: List of candlestick data

        Raises:
            requests.exceptions.RequestException: If the request fails
        """
        params = {
            't': pair,
            'r': period,
            'limit': limit
        }
        if end:
            params['end'] = end

        try:
            # Direct request to socket URL instead of using _make_request
            response = requests.get(
                f"{self.config.socket_url}/graph/hist",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Candlestick request failed: {str(e)}")
            raise

    # Private API Methods - Account & Balance
    def get_balances(self) -> Dict:
        """
        Get account balances.

        Returns:
            Dict: Account balance information
        """
        return self._make_request('POST', '/private/balances', {}, private=True)

    def get_deposit_address(
            self,
            currency: str,
            network: Optional[str] = None,
            new: bool = False
    ) -> Dict:
        """
        Get deposit address for a currency.

        Args:
            currency: Currency code
            network: Optional network type
            new: Whether to generate new address

        Returns:
            Dict: Deposit address information
        """
        params = {
            'iso': currency,
            'new': int(new)
        }
        if network:
            params['network'] = network

        return self._make_request('POST', '/private/get-address', params, private=True)

    # Private API Methods - Order Management
    def create_order(
            self,
            pair: str,
            type_trade: TradeType,
            order_type: OrderType,
            volume: float,
            rate: Optional[float] = None,
            stop_rate: Optional[float] = None
    ) -> Dict:
        """
        Create a new order.

        Args:
            pair: Trading pair symbol (e.g., 'BTCUSDT')
            type_trade: Type of trade (LIMIT, MARKET, etc)
            order_type: Order type (BUY/SELL)
            volume: Order volume
            rate: Order rate (required for LIMIT and STOP_LIMIT orders)
            stop_rate: Stop rate (required for STOP_LIMIT orders)

        Returns:
            Dict: Order creation result

        Raises:
            ValueError: If required parameters are missing
        """
        params = {
            'pair': pair,
            'type_trade': type_trade.value,
            'type': order_type.value,
            'volume': str(volume)
        }

        if type_trade in [TradeType.LIMIT, TradeType.STOP_LIMIT]:
            if rate is None:
                raise ValueError("Rate is required for LIMIT and STOP_LIMIT orders")
            params['rate'] = str(rate)

        if type_trade == TradeType.STOP_LIMIT:
            if stop_rate is None:
                raise ValueError("Stop rate is required for STOP_LIMIT orders")
            params['stop_rate'] = str(stop_rate)

        return self._make_request('POST', '/private/create-order', params, private=True)

    def get_active_orders(self) -> List[Dict]:
        """
        Get list of active orders.

        Returns:
            List[Dict]: List of active orders
        """
        return self._make_request('POST', '/private/orders', {}, private=True)

    def get_order(self, order_id: int) -> Dict:
        """
        Get information about a specific order.

        Args:
            order_id: Order ID

        Returns:
            Dict: Order information
        """
        return self._make_request(
            'POST',
            '/private/get-order',
            {'order_id': str(order_id)},
            private=True
        )

    def cancel_order(self, order_id: int) -> Dict:
        """
        Cancel a specific order.

        Args:
            order_id: Order ID

        Returns:
            Dict: Cancellation result
        """
        return self._make_request(
            'POST',
            '/private/delete-order',
            {'order_id': str(order_id)},
            private=True
        )

    def cancel_multiple_orders(self, order_ids: List[int]) -> Dict:
        """
        Cancel multiple orders at once.

        Args:
            order_ids: List of order IDs to cancel

        Returns:
            Dict: Cancellation results

        Raises:
            ValueError: If more than 50 orders are provided
        """
        if len(order_ids) > 50:
            raise ValueError("Maximum 50 orders can be cancelled at once")
        return self._make_request(
            'POST',
            '/private/delete-orders',
            {'list': order_ids},
            private=True
        )

    def get_order_history(
            self,
            page: int = 1,
            limit: int = 2000,
            pair_id: Optional[int] = None,
            format_number: bool = False
    ) -> Dict:
        """
        Get order history.

        Args:
            page: Page number
            limit: Items per page (max 2000)
            pair_id: Filter by pair ID
            format_number: Return numbers as floats instead of integers

        Returns:
            Dict: Order history data
        """
        params = {
            'page': page,
            'limit': limit,
            'format_number': int(format_number)
        }
        if pair_id:
            params['pair_id'] = pair_id

        return self._make_request('POST', '/private/history', params, private=True)

    # Private API Methods - Withdrawal
    def create_withdrawal(
            self,
            currency: str,
            amount: float,
            address: str,
            network_type: Optional[int] = None,
            comment: Optional[str] = None,
            fee_from_amount: bool = False
    ) -> Dict:
        """
        Create a withdrawal request.

        Args:
            currency: Currency code
            amount: Withdrawal amount
            address: Destination address
            network_type: Optional network type
            comment: Optional comment or memo
            fee_from_amount: Whether to deduct fee from amount

        Returns:
            Dict: Withdrawal creation result
        """
        params = {
            'iso': currency,
            'amount': amount,
            'to_address': address,
            'fee_from_amount': int(fee_from_amount)
        }
        if network_type is not None:
            params['network_type'] = network_type
        if comment:
            params['comment'] = comment

        return self._make_request('POST', '/withdraw', params, private=True)

    def confirm_withdrawal(
            self,
            withdrawal_id: int,
            email_pin: str,
            google_pin: Optional[str] = None
    ) -> Dict:
        """
        Confirm a withdrawal request.

        Args:
            withdrawal_id: Withdrawal ID
            email_pin: Email confirmation code
            google_pin: Google 2FA code (if enabled)

        Returns:
            Dict: Confirmation result
        """
        params = {
            'id': withdrawal_id,
            'email_pin': email_pin
        }
        if google_pin:
            params['google_pin'] = google_pin

        return self._make_request('POST', '/withdraw/confirm-code', params, private=True)

    def resend_withdrawal_pin(self, withdrawal_id: int) -> Dict:
        """
        Resend withdrawal confirmation email.

        Args:
            withdrawal_id: Withdrawal ID

        Returns:
            Dict: Operation result
        """
        return self._make_request(
            'POST',
            '/withdraw/send-pin',
            {'id': withdrawal_id},
            private=True
        )

    # WebSocket Methods
    def connect_websocket(self):
        """Connect to WebSocket API"""
        self.ws.connect()

    def subscribe_orderbook(self, pair_id: int):
        """
        Subscribe to order book updates.

        Args:
            pair_id: Trading pair ID
        """
        self.ws.subscribe_orderbook(pair_id)

    def subscribe_trades(self, pair_id: int):
        """
        Subscribe to trade updates.

        Args:
            pair_id: Trading pair ID
        """
        self.ws.subscribe_trades(pair_id)

    def subscribe_candlesticks(self, pair: str, period: str, pair_id: int):
        """
        Subscribe to candlestick updates.

        Args:
            pair: Trading pair symbol (e.g., 'BTCUSDT')
            period: Time period ('60' for 1h, 'D' for 1d, 'W' for 1w)
            pair_id: Trading pair ID
        """
        self.ws.subscribe_candlesticks(pair, period, pair_id)

    def unsubscribe(self, event: str):
        """
        Unsubscribe from a WebSocket event.

        Args:
            event: Event name to unsubscribe from
        """
        self.ws.unsubscribe(event)
