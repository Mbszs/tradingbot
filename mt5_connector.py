"""
MetaTrader 5 Connector
Handles all MT5 connections, data loading, and trade execution
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import logging


class MT5Connector:
    """MetaTrader 5 connection and trading interface"""
    
    def __init__(self, symbol: str = "XAUUSD", magic_number: int = 234000):
        """
        Initialize MT5 connector
        
        Args:
            symbol: Trading symbol (default: XAUUSD)
            magic_number: Unique identifier for bot's trades
        """
        self.symbol = symbol
        self.magic_number = magic_number
        self.logger = logging.getLogger(__name__)
        self.connected = False
        
        # Timeframe mapping
        self.timeframe_map = {
            '1m': mt5.TIMEFRAME_M1,
            '5m': mt5.TIMEFRAME_M5,
            '15m': mt5.TIMEFRAME_M15,
            '30m': mt5.TIMEFRAME_M30,
            '1h': mt5.TIMEFRAME_H1,
            '4h': mt5.TIMEFRAME_H4,
            '1d': mt5.TIMEFRAME_D1,
            '1w': mt5.TIMEFRAME_W1,
            '1M': mt5.TIMEFRAME_MN1
        }
    
    def connect(self, login: int = None, password: str = None, 
                server: str = None) -> bool:
        """
        Connect to MT5 terminal
        
        Args:
            login: MT5 account number (optional if already logged in)
            password: Account password
            server: Broker server name
            
        Returns:
            True if connection successful
        """
        try:
            # Initialize MT5
            if not mt5.initialize():
                self.logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                return False
            
            # Login if credentials provided
            if login and password and server:
                if not mt5.login(login, password, server):
                    self.logger.error(f"MT5 login failed: {mt5.last_error()}")
                    mt5.shutdown()
                    return False
                self.logger.info(f"Logged in to MT5 account {login} on {server}")
            else:
                # Use existing login
                account_info = mt5.account_info()
                if account_info is None:
                    self.logger.error("No active MT5 login found")
                    mt5.shutdown()
                    return False
                self.logger.info(f"Using existing MT5 login: {account_info.login}")
            
            # Verify symbol
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                self.logger.error(f"Symbol {self.symbol} not found")
                mt5.shutdown()
                return False
            
            # Enable symbol if not visible
            if not symbol_info.visible:
                if not mt5.symbol_select(self.symbol, True):
                    self.logger.error(f"Failed to select symbol {self.symbol}")
                    mt5.shutdown()
                    return False
            
            self.connected = True
            self.logger.info(f"MT5 connected successfully - Symbol: {self.symbol}")
            
            # Display account info
            account = mt5.account_info()
            self.logger.info(f"Account Balance: ${account.balance:.2f}")
            self.logger.info(f"Account Equity: ${account.equity:.2f}")
            self.logger.info(f"Account Leverage: 1:{account.leverage}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to MT5: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            self.logger.info("Disconnected from MT5")
    
    def get_historical_data(self, timeframe: str, bars: int = 500) -> pd.DataFrame:
        """
        Get historical OHLCV data from MT5
        
        Args:
            timeframe: Timeframe string ('1h', '4h', '1d', etc.)
            bars: Number of bars to retrieve
            
        Returns:
            DataFrame with OHLCV data
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return pd.DataFrame()
        
        try:
            mt5_timeframe = self.timeframe_map.get(timeframe, mt5.TIMEFRAME_H1)
            
            # Get data
            rates = mt5.copy_rates_from_pos(self.symbol, mt5_timeframe, 0, bars)
            
            if rates is None or len(rates) == 0:
                self.logger.error(f"Failed to get rates: {mt5.last_error()}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            
            # Convert time to datetime
            df['timestamp'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('timestamp', inplace=True)
            
            # Rename columns
            df = df[['open', 'high', 'low', 'close', 'tick_volume']].rename(
                columns={'tick_volume': 'volume'}
            )
            
            self.logger.debug(f"Retrieved {len(df)} bars of {timeframe} data")
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting historical data: {e}")
            return pd.DataFrame()
    
    def get_current_price(self) -> Dict[str, float]:
        """
        Get current bid/ask prices
        
        Returns:
            Dict with 'bid', 'ask', 'spread'
        """
        if not self.connected:
            return {}
        
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                self.logger.error(f"Failed to get tick: {mt5.last_error()}")
                return {}
            
            return {
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': tick.ask - tick.bid,
                'time': datetime.fromtimestamp(tick.time)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting current price: {e}")
            return {}
    
    def get_symbol_info(self) -> Dict:
        """Get symbol specifications"""
        if not self.connected:
            return {}
        
        try:
            info = mt5.symbol_info(self.symbol)
            if info is None:
                return {}
            
            return {
                'point': info.point,
                'digits': info.digits,
                'spread': info.spread,
                'volume_min': info.volume_min,
                'volume_max': info.volume_max,
                'volume_step': info.volume_step,
                'contract_size': info.trade_contract_size,
                'margin_initial': info.margin_initial,
                'trade_mode': info.trade_mode
            }
            
        except Exception as e:
            self.logger.error(f"Error getting symbol info: {e}")
            return {}
    
    def calculate_lot_size(self, risk_amount: float, stop_loss_points: float) -> float:
        """
        Calculate lot size based on risk
        
        Args:
            risk_amount: Dollar amount to risk
            stop_loss_points: Stop loss distance in points
            
        Returns:
            Lot size rounded to symbol's volume step
        """
        try:
            symbol_info = self.get_symbol_info()
            
            if not symbol_info:
                return 0.01
            
            # Calculate lot size
            # For XAUUSD: 1 lot = 100 oz, 1 point = $0.01
            point_value = symbol_info['contract_size'] * symbol_info['point']
            lot_size = risk_amount / (stop_loss_points * point_value)
            
            # Round to volume step
            volume_step = symbol_info['volume_step']
            lot_size = round(lot_size / volume_step) * volume_step
            
            # Clamp to min/max
            lot_size = max(symbol_info['volume_min'], lot_size)
            lot_size = min(symbol_info['volume_max'], lot_size)
            
            return lot_size
            
        except Exception as e:
            self.logger.error(f"Error calculating lot size: {e}")
            return 0.01
    
    def open_position(self, position_type: str, volume: float, 
                     stop_loss: float = None, take_profit: float = None,
                     comment: str = "Trading Bot") -> Optional[int]:
        """
        Open a trading position
        
        Args:
            position_type: 'long' or 'short'
            volume: Lot size
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            comment: Order comment
            
        Returns:
            Position ticket number if successful, None otherwise
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return None
        
        try:
            # Get current price
            prices = self.get_current_price()
            if not prices:
                return None
            
            # Determine order type and price
            if position_type.lower() == 'long':
                order_type = mt5.ORDER_TYPE_BUY
                price = prices['ask']
            else:
                order_type = mt5.ORDER_TYPE_SELL
                price = prices['bid']
            
            # Get symbol info for filling mode
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                self.logger.error("Failed to get symbol info")
                return None
            
            # Determine filling mode
            filling_type = symbol_info.filling_mode
            if filling_type == 1:
                filling = mt5.ORDER_FILLING_FOK
            elif filling_type == 2:
                filling = mt5.ORDER_FILLING_IOC
            else:
                filling = mt5.ORDER_FILLING_RETURN
            
            # Prepare request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": self.magic_number,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            
            # Add SL/TP if provided
            if stop_loss:
                request["sl"] = stop_loss
            if take_profit:
                request["tp"] = take_profit
            
            # Send order
            result = mt5.order_send(request)
            
            if result is None:
                self.logger.error(f"Order send failed: {mt5.last_error()}")
                return None
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(f"Order failed: {result.comment} (code: {result.retcode})")
                return None
            
            self.logger.info(f"Position opened successfully:")
            self.logger.info(f"  Ticket: {result.order}")
            self.logger.info(f"  Type: {position_type.upper()}")
            self.logger.info(f"  Volume: {volume}")
            self.logger.info(f"  Price: {result.price}")
            self.logger.info(f"  SL: {stop_loss}")
            self.logger.info(f"  TP: {take_profit}")
            
            return result.order
            
        except Exception as e:
            self.logger.error(f"Error opening position: {e}")
            return None
    
    def close_position(self, ticket: int) -> bool:
        """
        Close a position by ticket number
        
        Args:
            ticket: Position ticket number
            
        Returns:
            True if closed successfully
        """
        if not self.connected:
            self.logger.error("Not connected to MT5")
            return False
        
        try:
            # Get position info
            position = mt5.positions_get(ticket=ticket)
            if position is None or len(position) == 0:
                self.logger.error(f"Position {ticket} not found")
                return False
            
            position = position[0]
            
            # Determine close order type
            if position.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(self.symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(self.symbol).ask
            
            # Get filling mode
            symbol_info = mt5.symbol_info(self.symbol)
            filling_type = symbol_info.filling_mode
            if filling_type == 1:
                filling = mt5.ORDER_FILLING_FOK
            elif filling_type == 2:
                filling = mt5.ORDER_FILLING_IOC
            else:
                filling = mt5.ORDER_FILLING_RETURN
            
            # Prepare close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": self.magic_number,
                "comment": "Close by bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            
            # Send close order
            result = mt5.order_send(request)
            
            if result is None:
                self.logger.error(f"Close order failed: {mt5.last_error()}")
                return False
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(f"Close failed: {result.comment} (code: {result.retcode})")
                return False
            
            self.logger.info(f"Position {ticket} closed successfully at {result.price}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return False
    
    def modify_position(self, ticket: int, stop_loss: float = None, 
                       take_profit: float = None) -> bool:
        """
        Modify position SL/TP
        
        Args:
            ticket: Position ticket number
            stop_loss: New stop loss (None = no change)
            take_profit: New take profit (None = no change)
            
        Returns:
            True if modified successfully
        """
        if not self.connected:
            return False
        
        try:
            # Get position
            position = mt5.positions_get(ticket=ticket)
            if position is None or len(position) == 0:
                self.logger.error(f"Position {ticket} not found")
                return False
            
            position = position[0]
            
            # Use existing values if not provided
            new_sl = stop_loss if stop_loss is not None else position.sl
            new_tp = take_profit if take_profit is not None else position.tp
            
            # Prepare modify request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": self.symbol,
                "position": ticket,
                "sl": new_sl,
                "tp": new_tp,
                "magic": self.magic_number,
            }
            
            # Send modify request
            result = mt5.order_send(request)
            
            if result is None:
                self.logger.error(f"Modify failed: {mt5.last_error()}")
                return False
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(f"Modify failed: {result.comment}")
                return False
            
            self.logger.info(f"Position {ticket} modified - SL: {new_sl}, TP: {new_tp}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error modifying position: {e}")
            return False
    
    def get_open_positions(self) -> List[Dict]:
        """
        Get all open positions for this bot (by magic number)
        
        Returns:
            List of position dictionaries
        """
        if not self.connected:
            return []
        
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if positions is None:
                return []
            
            # Filter by magic number
            bot_positions = []
            for pos in positions:
                if pos.magic == self.magic_number:
                    bot_positions.append({
                        'ticket': pos.ticket,
                        'type': 'long' if pos.type == mt5.POSITION_TYPE_BUY else 'short',
                        'volume': pos.volume,
                        'price_open': pos.price_open,
                        'price_current': pos.price_current,
                        'sl': pos.sl,
                        'tp': pos.tp,
                        'profit': pos.profit,
                        'time': datetime.fromtimestamp(pos.time),
                        'comment': pos.comment
                    })
            
            return bot_positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    def get_account_info(self) -> Dict:
        """Get account information"""
        if not self.connected:
            return {}
        
        try:
            account = mt5.account_info()
            if account is None:
                return {}
            
            return {
                'balance': account.balance,
                'equity': account.equity,
                'margin': account.margin,
                'free_margin': account.margin_free,
                'margin_level': account.margin_level,
                'profit': account.profit,
                'leverage': account.leverage,
                'currency': account.currency
            }
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return {}
    
    def partial_close(self, ticket: int, close_volume: float) -> bool:
        """
        Partially close a position
        
        Args:
            ticket: Position ticket
            close_volume: Volume to close (must be < total volume)
            
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            # Get position
            position = mt5.positions_get(ticket=ticket)
            if position is None or len(position) == 0:
                self.logger.error(f"Position {ticket} not found")
                return False
            
            position = position[0]
            
            if close_volume >= position.volume:
                self.logger.error("Close volume must be less than position volume")
                return False
            
            # Determine order type
            if position.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(self.symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(self.symbol).ask
            
            # Get filling mode
            symbol_info = mt5.symbol_info(self.symbol)
            filling_type = symbol_info.filling_mode
            if filling_type == 1:
                filling = mt5.ORDER_FILLING_FOK
            elif filling_type == 2:
                filling = mt5.ORDER_FILLING_IOC
            else:
                filling = mt5.ORDER_FILLING_RETURN
            
            # Prepare partial close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": close_volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": self.magic_number,
                "comment": "Partial close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            
            # Send order
            result = mt5.order_send(request)
            
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(f"Partial close failed: {result.comment if result else mt5.last_error()}")
                return False
            
            self.logger.info(f"Partially closed {close_volume} lots of position {ticket}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in partial close: {e}")
            return False


# Convenience function for quick connection
def quick_connect(symbol: str = "XAUUSD", magic_number: int = 234000) -> MT5Connector:
    """
    Quick connection to MT5 with default settings
    
    Returns:
        Connected MT5Connector instance
    """
    connector = MT5Connector(symbol, magic_number)
    if connector.connect():
        return connector
    return None
