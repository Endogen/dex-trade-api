# Dex-Trade API Python Client

A comprehensive Python client for interacting with the Dex-Trade cryptocurrency exchange API. This client provides access to all public and private API endpoints, including WebSocket support for real-time data.

## Features

- Complete implementation of the Dex-Trade API endpoints
- Real-time WebSocket support for market data
- Environment variable configuration support
- Built-in rate limiting and error handling
- Type hints for better IDE support
- Comprehensive error handling
- Well-documented examples for all API calls

## Installation

### Using pip

The simplest way to install the package is via pip:

```bash
pip install dex-trade-api
```

### Using Poetry (For Development)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/dex-trade-api.git
cd dex-trade-api
```

2. Install dependencies with Poetry:
```bash
poetry install
```

### From Source

```bash
git clone https://github.com/yourusername/dex-trade-api.git
cd dex-trade-api
pip install .
```

## Configuration

There are multiple ways to configure the API client with your credentials:

### 1. Using Environment Variables (.env file)

Create a `.env` file in your project directory:
```bash
# .env
DEXTRADE_LOGIN_TOKEN=your_login_token_here
DEXTRADE_SECRET=your_secret_here
```

Then initialize the client:
```python
from dextrade import DexTradeAPI

# Automatically loads from .env
client = DexTradeAPI.from_env()
```

### 2. Custom .env Location

```python
# Load from specific .env file
client = DexTradeAPI.from_env('/path/to/your/.env')
```

### 3. Direct Configuration

```python
from dextrade import DexTradeAPI, DexTradeConfig

config = DexTradeConfig(
    login_token="your_login_token",
    secret="your_secret"
)
client = DexTradeAPI(config)
```

## Usage Examples

### Public API Endpoints

#### Market Data

```python
# Get all available trading pairs
symbols = client.get_symbols()
print(f"Available pairs: {[symbol['pair'] for symbol in symbols]}")

# Get ticker information
ticker = client.get_ticker("BTCUSDT")
print(f"BTC/USDT Last Price: {ticker['last']}")
print(f"24h Volume: {ticker['volume_24H']}")

# Get order book
order_book = client.get_order_book("BTCUSDT")
print("Top 5 Bids:", order_book['data']['buy'][:5])
print("Top 5 Asks:", order_book['data']['sell'][:5])

# Get recent trades
trades = client.get_trade_history("BTCUSDT")
for trade in trades[:5]:
    print(f"Time: {datetime.fromtimestamp(trade['timestamp'])}")
    print(f"Price: {trade['rate']}, Volume: {trade['volume']}")
```

#### Candlestick Data

```python
# Get hourly candles for the last 100 hours
candles = client.get_candlesticks(
    pair="BTCUSDT",    # Trading pair
    period="60",       # Time period
    limit=100          # Number of candles
)

# Process candlestick data
# Note: Price values need to be divided by 10^8, volumes by 10^6
for candle in candles:
    print(f"Time: {datetime.fromtimestamp(candle['time'])}")
    print(f"Open: {candle['open'] / 1e8}")
    print(f"High: {candle['high'] / 1e8}")
    print(f"Low: {candle['low'] / 1e8}")
    print(f"Close: {candle['close'] / 1e8}")
    print(f"Volume: {candle['volume'] / 1e6}")
```

Available periods for candlesticks:
- `"60"` - 1 hour candles
- `"D"` - Daily candles
- `"W"` - Weekly candles

Error handling example:
```python
try:
    candles = client.get_candlesticks(pair="BTCUSDT", period="60")
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        print("Invalid trading pair or period")
    else:
        print(f"Request failed: {e}")
```

Important notes:
- Make sure to check available pairs using `get_symbols()` before requesting candlesticks
- Price values in responses are scaled by 10^8 and need to be divided
- Volume values are scaled by 10^6 and need to be divided
- The candlestick endpoint uses a different server (socket.dex-trade.com) than other REST endpoints

### Private API Endpoints

#### Account Information

```python
# Get all balances
balances = client.get_balances()
for balance in balances['data']['list']:
    if float(balance['balances']['total']) > 0:
        currency = balance['currency']['iso3']
        total = balance['balances']['total']
        available = balance['balances']['available']
        print(f"{currency}: Total={total}, Available={available}")

# Get deposit address
address = client.get_deposit_address(
    currency="BTC",
    network="BTC",  # Optional network type
    new=False       # Set to True to generate new address
)
print(f"Deposit address: {address['data']['address']}")
```

#### Order Management

```python
from dextrade import OrderType, TradeType

# Create a limit buy order
order = client.create_order(
    pair="BTCUSDT",
    type_trade=TradeType.LIMIT,
    order_type=OrderType.BUY,
    volume=0.001,        # Amount to buy
    rate=50000.0         # Limit price
)
print(f"Order created with ID: {order['data']['id']}")

# Create a market sell order
market_order = client.create_order(
    pair="BTCUSDT",
    type_trade=TradeType.MARKET,
    order_type=OrderType.SELL,
    volume=0.001
)

# Get all active orders
active_orders = client.get_active_orders()
for order in active_orders['data']['list']:
    print(f"Order {order['id']}: {order['pair']} - {order['volume']} @ {order['rate']}")

# Cancel an order
result = client.cancel_order(order_id=123456)
print(f"Cancel order result: {result['message']}")

# Cancel multiple orders
result = client.cancel_multiple_orders([123456, 123457])

# Get order history
history = client.get_order_history(
    page=1,
    limit=100,
    format_number=True  # Return formatted numbers
)
```

### WebSocket API

Connect to WebSocket and subscribe to updates:

```python
# Connect to WebSocket
client.connect_websocket()

# Subscribe to order book updates
client.subscribe_orderbook(pair_id=1)  # pair_id from symbols endpoint

# Subscribe to trade updates
client.subscribe_trades(pair_id=1)

# Subscribe to candlestick updates
client.subscribe_candlesticks(
    pair="BTCUSDT",
    period="60",  # 1 hour candles
    pair_id=1
)

# Unsubscribe from updates
client.unsubscribe("book_1")  # Event name format: "book_[pair_id]"
```

## Error Handling

The client includes comprehensive error handling:

```python
try:
    order = client.create_order(...)
except ValidationError as e:
    print(f"Invalid parameters: {e}")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
```

## Rate Limits

Please be aware of Dex-Trade's API rate limits:
- Public endpoints: 10 requests per second
- Private endpoints: 5 requests per second
- WebSocket connections: 1 connection per IP
