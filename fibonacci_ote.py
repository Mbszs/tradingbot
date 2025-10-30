"""
Fibonacci OTE (Optimal Trade Entry) Module
Calculates Fibonacci retracement levels for ICT OTE zones
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class FibonacciLevels:
    """Fibonacci retracement levels"""
    swing_high: float
    swing_high_idx: int
    swing_low: float
    swing_low_idx: int
    direction: str  # 'bullish' or 'bearish'
    
    # Standard Fibonacci levels
    level_0: float      # 0% (swing point)
    level_236: float    # 23.6%
    level_382: float    # 38.2%
    level_50: float     # 50%
    level_618: float    # 61.8% (OTE start)
    level_705: float    # 70.5%
    level_79: float     # 79% (OTE end)
    level_886: float    # 88.6%
    level_100: float    # 100% (other swing point)
    
    # OTE Zone (0.618 - 0.79)
    ote_high: float
    ote_low: float
    
    timestamp: pd.Timestamp


@dataclass
class OTEEntry:
    """Represents a potential OTE entry setup"""
    fib_levels: FibonacciLevels
    entry_price: float
    in_ote_zone: bool
    retracement_pct: float
    timestamp: pd.Timestamp


class FibonacciOTE:
    """
    Calculates Fibonacci retracement levels and identifies OTE zones
    
    OTE (Optimal Trade Entry) = 0.618 to 0.79 Fibonacci retracement zone
    This is considered the premium entry zone in ICT methodology
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.ote_min = config.get('fib_ote_min', 0.618)
        self.ote_max = config.get('fib_ote_max', 0.79)
        self.lookback = config.get('fib_lookback', 20)
    
    def calculate_fibonacci_levels(self, df: pd.DataFrame, 
                                   swing_high_idx: int, 
                                   swing_low_idx: int) -> FibonacciLevels:
        """
        Calculate Fibonacci retracement levels between two swing points
        
        Args:
            df: DataFrame with OHLC data
            swing_high_idx: Index of swing high
            swing_low_idx: Index of swing low
            
        Returns:
            FibonacciLevels object with all levels calculated
        """
        swing_high = df.iloc[swing_high_idx]['high']
        swing_low = df.iloc[swing_low_idx]['low']
        
        # Determine direction
        if swing_low_idx < swing_high_idx:
            direction = 'bullish'  # Low to High (uptrend retracement)
            price_range = swing_high - swing_low
            
            levels = {
                'level_0': swing_high,
                'level_236': swing_high - (price_range * 0.236),
                'level_382': swing_high - (price_range * 0.382),
                'level_50': swing_high - (price_range * 0.50),
                'level_618': swing_high - (price_range * 0.618),
                'level_705': swing_high - (price_range * 0.705),
                'level_79': swing_high - (price_range * 0.79),
                'level_886': swing_high - (price_range * 0.886),
                'level_100': swing_low
            }
            
            ote_high = levels['level_618']
            ote_low = levels['level_79']
            
        else:
            direction = 'bearish'  # High to Low (downtrend retracement)
            price_range = swing_high - swing_low
            
            levels = {
                'level_0': swing_low,
                'level_236': swing_low + (price_range * 0.236),
                'level_382': swing_low + (price_range * 0.382),
                'level_50': swing_low + (price_range * 0.50),
                'level_618': swing_low + (price_range * 0.618),
                'level_705': swing_low + (price_range * 0.705),
                'level_79': swing_low + (price_range * 0.79),
                'level_886': swing_low + (price_range * 0.886),
                'level_100': swing_high
            }
            
            ote_high = levels['level_79']
            ote_low = levels['level_618']
        
        return FibonacciLevels(
            swing_high=swing_high,
            swing_high_idx=swing_high_idx,
            swing_low=swing_low,
            swing_low_idx=swing_low_idx,
            direction=direction,
            ote_high=ote_high,
            ote_low=ote_low,
            timestamp=df.index[max(swing_high_idx, swing_low_idx)],
            **levels
        )
    
    def find_swing_points(self, df: pd.DataFrame, 
                         lookback: Optional[int] = None) -> Tuple[int, int]:
        """
        Find most recent swing high and swing low
        
        Args:
            df: DataFrame with OHLC data
            lookback: Number of bars to look back (uses config default if None)
            
        Returns:
            Tuple of (swing_high_idx, swing_low_idx)
        """
        if lookback is None:
            lookback = self.lookback
        
        # Use only recent data
        start_idx = max(0, len(df) - lookback)
        recent_df = df.iloc[start_idx:]
        
        # Find swing high and low
        swing_high_idx = recent_df['high'].idxmax()
        swing_low_idx = recent_df['low'].idxmin()
        
        # Convert to original DataFrame indices
        swing_high_pos = df.index.get_loc(swing_high_idx)
        swing_low_pos = df.index.get_loc(swing_low_idx)
        
        return swing_high_pos, swing_low_pos
    
    def check_ote_entry(self, df: pd.DataFrame, 
                       current_idx: int, 
                       fib_levels: FibonacciLevels) -> OTEEntry:
        """
        Check if current price is in OTE zone
        
        Args:
            df: DataFrame with OHLC data
            current_idx: Current bar index
            fib_levels: Pre-calculated Fibonacci levels
            
        Returns:
            OTEEntry object with entry details
        """
        current_bar = df.iloc[current_idx]
        current_price = current_bar['close']
        
        # Check if in OTE zone
        in_ote = (current_price >= min(fib_levels.ote_high, fib_levels.ote_low) and 
                 current_price <= max(fib_levels.ote_high, fib_levels.ote_low))
        
        # Calculate retracement percentage
        price_range = abs(fib_levels.swing_high - fib_levels.swing_low)
        
        if fib_levels.direction == 'bullish':
            retracement = (fib_levels.swing_high - current_price) / price_range
        else:
            retracement = (current_price - fib_levels.swing_low) / price_range
        
        retracement_pct = retracement * 100
        
        return OTEEntry(
            fib_levels=fib_levels,
            entry_price=current_price,
            in_ote_zone=in_ote,
            retracement_pct=retracement_pct,
            timestamp=df.index[current_idx]
        )
    
    def get_ote_zone_for_latest_swing(self, df: pd.DataFrame) -> FibonacciLevels:
        """
        Get OTE zone for the most recent swing high/low
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            FibonacciLevels object
        """
        swing_high_idx, swing_low_idx = self.find_swing_points(df)
        return self.calculate_fibonacci_levels(df, swing_high_idx, swing_low_idx)
    
    def is_price_in_discount(self, current_price: float, 
                            fib_levels: FibonacciLevels) -> bool:
        """
        Check if price is in discount zone (below 50% for bullish, above 50% for bearish)
        
        Args:
            current_price: Current market price
            fib_levels: Fibonacci levels
            
        Returns:
            True if in discount zone
        """
        if fib_levels.direction == 'bullish':
            return current_price < fib_levels.level_50
        else:
            return False  # In downtrend, we don't look for discount
    
    def is_price_in_premium(self, current_price: float, 
                           fib_levels: FibonacciLevels) -> bool:
        """
        Check if price is in premium zone (above 50% for bearish, below 50% for bullish)
        
        Args:
            current_price: Current market price
            fib_levels: Fibonacci levels
            
        Returns:
            True if in premium zone
        """
        if fib_levels.direction == 'bearish':
            return current_price > fib_levels.level_50
        else:
            return False  # In uptrend, we don't look for premium
    
    def get_fib_summary(self, df: pd.DataFrame) -> Dict:
        """
        Get comprehensive Fibonacci analysis summary
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Dictionary with Fibonacci analysis
        """
        fib_levels = self.get_ote_zone_for_latest_swing(df)
        current_price = df.iloc[-1]['close']
        
        ote_entry = self.check_ote_entry(df, len(df) - 1, fib_levels)
        
        return {
            'fib_levels': fib_levels,
            'current_price': current_price,
            'in_ote_zone': ote_entry.in_ote_zone,
            'retracement_pct': ote_entry.retracement_pct,
            'in_discount': self.is_price_in_discount(current_price, fib_levels),
            'in_premium': self.is_price_in_premium(current_price, fib_levels),
            'direction': fib_levels.direction
        }
