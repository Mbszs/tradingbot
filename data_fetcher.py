"""
Data Fetcher Module
Handles fetching OHLC data from various sources
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging


class DataFetcher:
    """
    Fetch market data from various sources
    
    Supported sources:
    - MetaTrader 5
    - Yahoo Finance (for historical data)
    - Oanda
    - Interactive Brokers
    - CSV files
    """
    
    def __init__(self, source: str = 'mt5', config: Optional[Dict] = None):
        """
        Initialize data fetcher
        
        Args:
            source: Data source ('mt5', 'yahoo', 'oanda', 'csv')
            config: Configuration dictionary
        """
        self.source = source.lower()
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize source
        if self.source == 'mt5':
            self._init_mt5()
        elif self.source == 'oanda':
            self._init_oanda()
    
    def _init_mt5(self):
        """Initialize MetaTrader 5 connection"""
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
            
            if not mt5.initialize():
                self.logger.error("Failed to initialize MT5")
                return
            
            # Login if credentials provided
            if 'login' in self.config:
                if not mt5.login(
                    self.config['login'],
                    self.config['password'],
                    self.config['server']
                ):
                    self.logger.error("Failed to login to MT5")
                else:
                    self.logger.info("Successfully connected to MT5")
        
        except ImportError:
            self.logger.error("MetaTrader5 package not installed")
    
    def _init_oanda(self):
        """Initialize Oanda connection"""
        try:
            import oandapyV20
            from oandapyV20 import API
            
            if 'api_token' not in self.config:
                self.logger.error("Oanda API token not provided")
                return
            
            self.oanda_client = API(access_token=self.config['api_token'])
            self.logger.info("Successfully initialized Oanda API")
        
        except ImportError:
            self.logger.error("oandapyV20 package not installed")
    
    def fetch_ohlc(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        """
        Fetch OHLC data from configured source
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            bars: Number of bars to fetch
            
        Returns:
            DataFrame with OHLC data
        """
        if self.source == 'mt5':
            return self._fetch_mt5_data(symbol, timeframe, bars)
        elif self.source == 'yahoo':
            return self._fetch_yahoo_data(symbol, timeframe, bars)
        elif self.source == 'oanda':
            return self._fetch_oanda_data(symbol, timeframe, bars)
        elif self.source == 'csv':
            return self._fetch_csv_data(symbol, timeframe)
        else:
            raise ValueError(f"Unsupported data source: {self.source}")
    
    def _fetch_mt5_data(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        """
        Fetch data from MetaTrader 5
        
        Args:
            symbol: Symbol name (e.g., 'XAUUSD')
            timeframe: Timeframe string ('1m', '5m', '15m', '1h', '4h', '1d')
            bars: Number of bars
            
        Returns:
            DataFrame with OHLC data
        """
        if not hasattr(self, 'mt5'):
            self.logger.error("MT5 not initialized")
            return pd.DataFrame()
        
        # Map timeframe strings to MT5 constants
        timeframe_map = {
            '1m': self.mt5.TIMEFRAME_M1,
            '5m': self.mt5.TIMEFRAME_M5,
            '15m': self.mt5.TIMEFRAME_M15,
            '30m': self.mt5.TIMEFRAME_M30,
            '1h': self.mt5.TIMEFRAME_H1,
            '4h': self.mt5.TIMEFRAME_H4,
            '1d': self.mt5.TIMEFRAME_D1
        }
        
        tf = timeframe_map.get(timeframe.lower())
        if tf is None:
            self.logger.error(f"Invalid timeframe: {timeframe}")
            return pd.DataFrame()
        
        # Fetch data
        rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, bars)
        
        if rates is None or len(rates) == 0:
            self.logger.error(f"Failed to fetch data for {symbol}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        # Rename columns
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        
        return df[['open', 'high', 'low', 'close', 'volume']]
    
    def _fetch_yahoo_data(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        """
        Fetch data from Yahoo Finance
        
        Args:
            symbol: Yahoo symbol (e.g., 'GC=F' for Gold)
            timeframe: Timeframe string
            bars: Number of bars
            
        Returns:
            DataFrame with OHLC data
        """
        try:
            import yfinance as yf
            
            # Map symbol
            symbol_map = {
                'XAUUSD': 'GC=F',  # Gold futures
                'EURUSD': 'EURUSD=X',
                'GBPUSD': 'GBPUSD=X'
            }
            
            yahoo_symbol = symbol_map.get(symbol, symbol)
            
            # Calculate period
            period_map = {
                '1m': '1mo',
                '5m': '1mo',
                '15m': '1mo',
                '1h': '3mo',
                '4h': '6mo',
                '1d': '2y'
            }
            
            period = period_map.get(timeframe.lower(), '1y')
            interval_map = {
                '1m': '1m',
                '5m': '5m',
                '15m': '15m',
                '30m': '30m',
                '1h': '1h',
                '4h': '1h',  # Yahoo doesn't have 4h, resample from 1h
                '1d': '1d'
            }
            
            interval = interval_map.get(timeframe.lower(), '1h')
            
            # Fetch data
            df = yf.download(yahoo_symbol, period=period, interval=interval, progress=False)
            
            if df.empty:
                self.logger.error(f"No data returned for {symbol}")
                return pd.DataFrame()
            
            # Rename columns
            df.columns = df.columns.str.lower()
            
            # Resample to 4h if needed
            if timeframe.lower() == '4h':
                df = df.resample('4H').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
            
            # Return only requested number of bars
            df = df.tail(bars)
            
            return df[['open', 'high', 'low', 'close', 'volume']]
        
        except ImportError:
            self.logger.error("yfinance package not installed")
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error fetching Yahoo data: {e}")
            return pd.DataFrame()
    
    def _fetch_oanda_data(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        """
        Fetch data from Oanda
        
        Args:
            symbol: Oanda instrument (e.g., 'XAU_USD')
            timeframe: Timeframe string
            bars: Number of bars
            
        Returns:
            DataFrame with OHLC data
        """
        if not hasattr(self, 'oanda_client'):
            self.logger.error("Oanda client not initialized")
            return pd.DataFrame()
        
        # Implementation would go here
        # Requires oandapyV20.endpoints.instruments.InstrumentsCandles
        
        self.logger.warning("Oanda data fetching not fully implemented")
        return pd.DataFrame()
    
    def _fetch_csv_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Load data from CSV file
        
        Args:
            symbol: Symbol name
            timeframe: Timeframe string
            
        Returns:
            DataFrame with OHLC data
        """
        filename = f"data/{symbol}_{timeframe}.csv"
        
        try:
            df = pd.read_csv(filename, index_col=0, parse_dates=True)
            
            # Ensure required columns exist
            required_cols = ['open', 'high', 'low', 'close']
            if not all(col in df.columns for col in required_cols):
                self.logger.error(f"CSV missing required columns: {required_cols}")
                return pd.DataFrame()
            
            return df
        
        except FileNotFoundError:
            self.logger.error(f"CSV file not found: {filename}")
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Error reading CSV: {e}")
            return pd.DataFrame()
    
    def fetch_multi_timeframe(self, symbol: str, 
                             timeframes: Dict[str, str],
                             bars: Dict[str, int]) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple timeframes
        
        Args:
            symbol: Trading symbol
            timeframes: Dict mapping names to timeframe strings
            bars: Dict mapping names to number of bars
            
        Returns:
            Dictionary of DataFrames
        """
        data = {}
        
        for name, tf in timeframes.items():
            num_bars = bars.get(name, 500)
            df = self.fetch_ohlc(symbol, tf, num_bars)
            
            if not df.empty:
                data[name] = df
                self.logger.info(f"Fetched {len(df)} bars for {name} ({tf})")
            else:
                self.logger.warning(f"Failed to fetch data for {name} ({tf})")
        
        return data
    
    def shutdown(self):
        """Cleanup and close connections"""
        if hasattr(self, 'mt5'):
            self.mt5.shutdown()
            self.logger.info("MT5 connection closed")


# Example usage
if __name__ == "__main__":
    # Example with Yahoo Finance (no authentication required)
    fetcher = DataFetcher(source='yahoo')
    
    # Fetch Gold data
    df = fetcher.fetch_ohlc('XAUUSD', '1h', 500)
    
    if not df.empty:
        print("Successfully fetched data:")
        print(df.tail())
        print(f"\nShape: {df.shape}")
    else:
        print("Failed to fetch data")
