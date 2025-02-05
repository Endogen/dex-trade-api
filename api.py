import requests
import time
import hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

class OrderType(Enum):
    BUY = 0
    SELL = 1

class TradeType(Enum):
    LIMIT = 0
    MARKET = 1
    STOP_LIMIT = 2
    QUICK_MARKET = 3
    HIDDEN_LIMIT = 4

@dataclass
class DexTradeConfig:
    """Configuration for DexTrade API client"""
    base_url: str = "https://api.dex-trade.com/v1"
    socket_url: str = "https://socket.dex-trade.com"
    login_token: Optional[str] = None
    secret: Optional[str] = None

class DexTradeAPI:
    """
    Python client for the Dex-Trade API
    
    Attributes:
        config (DexTradeConfig): Configuration object containing API credentials and URLs
    """
    
    def __init__(self, config: DexTradeConfig):
        self.config = config
        self.session = requests.Session()
        if config.login_token:
            self.session.headers.update({
                'login-token': config.login_token,
                'content-type': 'application/json'
            })

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate signature for private API requests
        
        Args:
            params: Request parameters to sign
            
        Returns:
            str: Generated signature
        """
        if not self.config.secret:
            raise ValueError("Secret key is required for private API calls")
            
        # Sort parameters alphabetically
        sorted_params = dict(sorted(params.items()))
        
        # Convert nested objects to sorted format
        values = []
        for key, value in sorted_params.items():
            if isinstance(value, dict):
                nested_sorted = dict(sorted(value.items()))
                values.extend(str(v) for v in nested_sorted.values())
            else:
                values.append(str(value))
                
        # Add secret and create signature
        values_str = ''.join(values) + self.config.secret
        return hashlib.sha256(values_str.encode()).hexdigest()

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                     private: bool = False) -> Dict:
        """
        Make HTTP request to API
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Request parameters
            private: Whether this is a private API call requiring authentication
            
        Returns:
            Dict: API response
        """
        url = f"{self.config.base_url}{endpoint}"
        
        if private:
            if not params:
                params = {}
            if 'request_id' not in params:
                params['request_id'] = str(int(time.time() * 1000000))
                
            signature = self._generate_signature(params)
            self.session.headers.update({'x-auth-sign': signature})
            
        if method == 'GET':
            response = self.session.get(url, params=params)
        else:
            response = self.session.post(url, json=params)
            
        response.raise_for_status()
        return response.json()

    # Public API Methods
    def get_symbols(self) -> List[Dict]:
        """Get list of available trading pairs"""
        response = self._make_request('GET', '/public/symbols')
        return response['data']

    def get_ticker(self, pair: str) -> Dict:
        """
        Get ticker information for a trading pair
        
        Args:
            pair: Trading pair symbol (e.g. 'BTCUSDT')
        """
        return self._make_request('GET', '/public/ticker', {'pair': pair})

    def get_order_book(self, pair: str) -> Dict:
        """
        Get order book for a trading pair
        
        Args:
            pair: Trading pair symbol (e.g. 'BTCUSDT')
        """
        return self._make_request('GET', '/public/book', {'pair': pair})

    def get_trade_history(self, pair: str) -> List[Dict]:
        """
        Get trade history for a trading pair
        
        Args:
            pair: Trading pair symbol (e.g. 'BTCUSDT')
        """
        return self._make_request('GET', '/public/trades', {'pair': pair})

    # Private API Methods
    def create_order(self, pair: str, type_trade: TradeType, order_type: OrderType, 
                    volume: float, rate: Optional[float] = None,
                    stop_rate: Optional[float] = None) -> Dict:
        """
        Create a new order
        
        Args:
            pair: Trading pair symbol (e.g. 'BTCUSDT')
            type_trade: Type of trade (LIMIT, MARKET, etc)
            order_type: Order type (BUY/SELL)
            volume: Order volume
            rate: Order rate (required for LIMIT and STOP_LIMIT orders)
            stop_rate: Stop rate (required for STOP_LIMIT orders)
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
        """Get list of active orders"""
        return self._make_request('POST', '/private/orders', {}, private=True)

    def get_order(self, order_id: int) -> Dict:
        """
        Get information about a specific order
        
        Args:
            order_id: Order ID
        """
        return self._make_request('POST', '/private/get-order', 
                                {'order_id': str(order_id)}, private=True)

    def cancel_order(self, order_id: int) -> Dict:
        """
        Cancel a specific order
        
        Args:
            order_id: Order ID
        """
        return self._make_request('POST', '/private/delete-order', 
                                {'order_id': str(order_id)}, private=True)

    def get_balances(self) -> Dict:
        """Get account balances"""
        return self._make_request('POST', '/private/balances', {}, private=True)

    def get_deposit_address(self, currency: str, network: Optional[str] = None, 
                          new: bool = False) -> Dict:
        """
        Get deposit address for a currency
        
        Args:
            currency: Currency code
            network: Network type (optional)
            new: Whether to generate new address
        """
        params = {
            'iso': currency,
            'new': int(new)
        }
        if network:
            params['network'] = network
            
        return self._make_request('POST', '/private/get-address', params, private=True)

# Usage example:
if __name__ == "__main__":
    # Initialize client
    config = DexTradeConfig(
        login_token="token",
        secret="secret"
    )
    client = DexTradeAPI(config)
    
    # Public API examples
    symbols = client.get_symbols()
    btc_ticker = client.get_ticker("BTCUSDT")
    order_book = client.get_order_book("BTCUSDT")
    
    # Private API examples
    balances = client.get_balances()

    # Create a limit buy order
    order = client.create_order(
        pair="BTCUSDT",
        type_trade=TradeType.LIMIT,
        order_type=OrderType.BUY,
        volume=0.001,
        rate=50000.0
    )

