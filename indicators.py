"""
Technical Indicators Module
Implements all quantitative indicators for the trading bot
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict


class TechnicalIndicators:
    """Technical indicator calculations"""
    
    @staticmethod
    def calculate_ema(data: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_sma(data: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average"""
        return data.rolling(window=period).mean()
    
    @staticmethod
    def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, 
                      signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD indicator
        Returns: (macd_line, signal_line, histogram)
        """
        ema_fast = TechnicalIndicators.calculate_ema(data, fast)
        ema_slow = TechnicalIndicators.calculate_ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, 
                     period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = pd.Series(true_range).rolling(window=period).mean()
        return atr
    
    @staticmethod
    def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """Calculate On-Balance Volume"""
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        return obv
    
    @staticmethod
    def calculate_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
        """Calculate Volume Simple Moving Average"""
        return volume.rolling(window=period).mean()
    
    @staticmethod
    def detect_macd_crossover(macd_line: pd.Series, signal_line: pd.Series, 
                             histogram: pd.Series = None,
                             require_expansion: bool = False) -> Dict[str, bool]:
        """
        Detect MACD crossovers
        Returns dict with 'bullish' and 'bearish' signals
        """
        crossover_up = (macd_line.iloc[-2] <= signal_line.iloc[-2] and 
                       macd_line.iloc[-1] > signal_line.iloc[-1])
        crossover_down = (macd_line.iloc[-2] >= signal_line.iloc[-2] and 
                         macd_line.iloc[-1] < signal_line.iloc[-1])
        
        # Check histogram expansion if required
        if require_expansion and histogram is not None:
            hist_expanding = abs(histogram.iloc[-1]) > abs(histogram.iloc[-2])
            crossover_up = crossover_up and hist_expanding
            crossover_down = crossover_down and hist_expanding
        
        return {
            'bullish': crossover_up,
            'bearish': crossover_down
        }
    
    @staticmethod
    def check_ma_ribbon_alignment(ema_20: pd.Series, ema_50: pd.Series, 
                                  ema_200: pd.Series) -> Dict[str, bool]:
        """
        Check if MA ribbon is aligned for trend
        Bullish: EMA20 > EMA50 > EMA200
        Bearish: EMA20 < EMA50 < EMA200
        """
        bullish = (ema_20.iloc[-1] > ema_50.iloc[-1] > ema_200.iloc[-1])
        bearish = (ema_20.iloc[-1] < ema_50.iloc[-1] < ema_200.iloc[-1])
        
        return {
            'bullish_aligned': bullish,
            'bearish_aligned': bearish,
            'neutral': not (bullish or bearish)
        }
    
    @staticmethod
    def check_volume_spike(volume: pd.Series, volume_ma: pd.Series, 
                          threshold: float = 1.2) -> bool:
        """Check if current volume is spiking (threshold * average)"""
        return volume.iloc[-1] > (volume_ma.iloc[-1] * threshold)
    
    @staticmethod
    def check_obv_trend(obv: pd.Series, lookback: int = 5) -> str:
        """
        Check OBV trend direction
        Returns: 'rising', 'falling', or 'neutral'
        """
        recent_obv = obv.iloc[-lookback:]
        obv_slope = np.polyfit(range(len(recent_obv)), recent_obv, 1)[0]
        
        if obv_slope > 0:
            return 'rising'
        elif obv_slope < 0:
            return 'falling'
        else:
            return 'neutral'


class PriceActionDetector:
    """Detect price action patterns"""
    
    @staticmethod
    def is_bullish_engulfing(df: pd.DataFrame, index: int = -1) -> bool:
        """Detect bullish engulfing pattern"""
        if index < -len(df) + 1:
            return False
        
        current = df.iloc[index]
        previous = df.iloc[index - 1]
        
        # Previous candle bearish, current bullish
        prev_bearish = previous['close'] < previous['open']
        curr_bullish = current['close'] > current['open']
        
        # Current body engulfs previous body
        engulfing = (current['open'] <= previous['close'] and 
                    current['close'] >= previous['open'])
        
        return prev_bearish and curr_bullish and engulfing
    
    @staticmethod
    def is_bearish_engulfing(df: pd.DataFrame, index: int = -1) -> bool:
        """Detect bearish engulfing pattern"""
        if index < -len(df) + 1:
            return False
        
        current = df.iloc[index]
        previous = df.iloc[index - 1]
        
        # Previous candle bullish, current bearish
        prev_bullish = previous['close'] > previous['open']
        curr_bearish = current['close'] < current['open']
        
        # Current body engulfs previous body
        engulfing = (current['open'] >= previous['close'] and 
                    current['close'] <= previous['open'])
        
        return prev_bullish and curr_bearish and engulfing
    
    @staticmethod
    def is_hammer(df: pd.DataFrame, index: int = -1) -> bool:
        """Detect hammer pattern (bullish reversal)"""
        candle = df.iloc[index]
        
        body = abs(candle['close'] - candle['open'])
        total_range = candle['high'] - candle['low']
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        
        if total_range == 0:
            return False
        
        # Lower wick at least 2x body, small upper wick
        return (lower_wick >= body * 2 and 
                upper_wick <= body * 0.3 and
                body / total_range <= 0.3)
    
    @staticmethod
    def is_shooting_star(df: pd.DataFrame, index: int = -1) -> bool:
        """Detect shooting star pattern (bearish reversal)"""
        candle = df.iloc[index]
        
        body = abs(candle['close'] - candle['open'])
        total_range = candle['high'] - candle['low']
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        
        if total_range == 0:
            return False
        
        # Upper wick at least 2x body, small lower wick
        return (upper_wick >= body * 2 and 
                lower_wick <= body * 0.3 and
                body / total_range <= 0.3)
    
    @staticmethod
    def is_pin_bar(df: pd.DataFrame, index: int = -1, direction: str = 'bullish') -> bool:
        """Detect pin bar pattern"""
        candle = df.iloc[index]
        
        body = abs(candle['close'] - candle['open'])
        total_range = candle['high'] - candle['low']
        lower_wick = min(candle['open'], candle['close']) - candle['low']
        upper_wick = candle['high'] - max(candle['open'], candle['close'])
        
        if total_range == 0:
            return False
        
        if direction == 'bullish':
            # Long lower wick (bullish rejection)
            return (lower_wick >= total_range * 0.6 and 
                   body / total_range <= 0.3)
        else:
            # Long upper wick (bearish rejection)
            return (upper_wick >= total_range * 0.6 and 
                   body / total_range <= 0.3)
