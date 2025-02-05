"""WebSocket client for the Dex-Trade API."""

import json
import logging
from typing import Optional, Callable, Dict, Any
from websocket import WebSocketApp
from threading import Thread, Event

logger = logging.getLogger(__name__)


class DexTradeWebSocket:
    """WebSocket client for Dex-Trade streaming API.

    This class handles real-time market data streaming including order book updates,
    trade history, and candlestick data.
    """

    def __init__(self, url: str, on_data: Optional[Callable[[str], None]] = None):
        """Initialize WebSocket client.

        Args:
            url: WebSocket endpoint URL
            on_data: Optional callback for data handling
        """
        self.url = url
        self.ws: Optional[WebSocketApp] = None
        self.on_data_callback = on_data
        self.connected = Event()
        self._thread: Optional[Thread] = None

    def connect(self):
        """Establish WebSocket connection in a separate thread."""
        if self.ws is None or not self.connected.is_set():
            self.ws = WebSocketApp(
                self.url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            self._thread = Thread(target=self._run_forever, daemon=True)
            self._thread.start()
            # Wait for connection to be established
            self.connected.wait(timeout=10)
            if not self.connected.is_set():
                raise ConnectionError("Failed to establish WebSocket connection")

    def disconnect(self):
        """Close WebSocket connection."""
        if self.ws:
            self.ws.close()
            self.connected.clear()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1)

    def _run_forever(self):
        """Run WebSocket connection in a loop with automatic reconnection."""
        while True:
            try:
                self.ws.run_forever()
                if not self.connected.is_set():
                    # Only break if we intentionally disconnected
                    break
                logger.info("WebSocket disconnected. Attempting to reconnect...")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    def subscribe_orderbook(self, pair_id: int):
        """Subscribe to orderbook updates.

        Args:
            pair_id: Trading pair ID
        """
        self._send_message({
            'type': 'book',
            'event': f'book_{pair_id}'
        })

    def subscribe_trades(self, pair_id: int):
        """Subscribe to trade history updates.

        Args:
            pair_id: Trading pair ID
        """
        self._send_message({
            'type': 'hist',
            'event': f'hist_{pair_id}'
        })

    def subscribe_candlesticks(self, pair: str, period: str, pair_id: int):
        """Subscribe to candlestick updates.

        Args:
            pair: Trading pair symbol (e.g., 'BTCUSDT')
            period: Time period ('60' for 1h, 'D' for 1d, 'W' for 1w)
            pair_id: Trading pair ID
        """
        self._send_message({
            'type': 'graph',
            'event': f'{pair}:{period}:{pair_id}'
        })

    def unsubscribe(self, event: str):
        """Unsubscribe from a specific event.

        Args:
            event: Event to unsubscribe from (e.g., 'book_1', 'hist_1')
        """
        self._send_message({
            'type': 'unsubscribe',
            'event': event
        })

    def _send_message(self, message: Dict[str, Any]):
        """Send message to WebSocket server.

        Args:
            message: Message to send
        """
        if not self.connected.is_set():
            raise ConnectionError("WebSocket is not connected")

        try:
            self.ws.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    def _on_message(self, ws, message: str):
        """Handle incoming WebSocket messages."""
        try:
            if self.on_data_callback:
                self.on_data_callback(message)
            else:
                data = json.loads(message)
                # Log message type and basic info
                msg_type = data.get('type')
                logger.debug(f"Received {msg_type} message")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        logger.error(f"WebSocket error: {error}")
        self.connected.clear()

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.connected.clear()

    def _on_open(self, ws):
        """Handle WebSocket connection open."""
        logger.info("WebSocket connection established")
        self.connected.set()

    def __enter__(self):
        """Context manager enter."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
