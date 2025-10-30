"""
Market Structure Analysis Module
Detects market structure, swing highs/lows, and trend direction
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class TrendDirection(Enum):
    """Trend direction enum"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class StructureType(Enum):
    """Market structure type"""
    HIGHER_HIGH = "higher_high"
    HIGHER_LOW = "higher_low"
    LOWER_HIGH = "lower_high"
    LOWER_LOW = "lower_low"
    EQUAL_HIGH = "equal_high"
    EQUAL_LOW = "equal_low"


@dataclass
class SwingPoint:
    """Swing high or low point"""
    index: int
    price: float
    point_type: str  # 'high' or 'low'
    strength: int  # Number of candles on each side confirming the swing


@dataclass
class StructureBreak:
    """Structure break event"""
    index: int
    break_type: StructureType
    previous_structure_price: float
    break_price: float
    confirmed: bool = False


class MarketStructure:
    """Analyze market structure and trend"""
    
    def __init__(self, config):
        self.config = config
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        self.structure_breaks: List[StructureBreak] = []
    
    def detect_swing_highs(self, df: pd.DataFrame, lookback: int = 10) -> List[SwingPoint]:
        """Detect swing high points"""
        swing_highs = []
        
        for i in range(lookback, len(df) - lookback):
            is_swing_high = True
            current_high = df.iloc[i]['high']
            
            # Check if this is a local high
            for j in range(1, lookback + 1):
                if (df.iloc[i - j]['high'] >= current_high or
                    df.iloc[i + j]['high'] >= current_high):
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing = SwingPoint(
                    index=i,
                    price=current_high,
                    point_type='high',
                    strength=lookback
                )
                swing_highs.append(swing)
        
        return swing_highs
    
    def detect_swing_lows(self, df: pd.DataFrame, lookback: int = 10) -> List[SwingPoint]:
        """Detect swing low points"""
        swing_lows = []
        
        for i in range(lookback, len(df) - lookback):
            is_swing_low = True
            current_low = df.iloc[i]['low']
            
            # Check if this is a local low
            for j in range(1, lookback + 1):
                if (df.iloc[i - j]['low'] <= current_low or
                    df.iloc[i + j]['low'] <= current_low):
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing = SwingPoint(
                    index=i,
                    price=current_low,
                    point_type='low',
                    strength=lookback
                )
                swing_lows.append(swing)
        
        return swing_lows
    
    def analyze_structure(self, swing_highs: List[SwingPoint], 
                         swing_lows: List[SwingPoint]) -> List[StructureType]:
        """
        Analyze market structure based on swing points
        Returns list of structure types in sequence
        """
        structure_sequence = []
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return structure_sequence
        
        # Analyze highs
        for i in range(1, len(swing_highs)):
            current = swing_highs[i]
            previous = swing_highs[i - 1]
            
            if current.price > previous.price:
                structure_sequence.append(StructureType.HIGHER_HIGH)
            elif current.price < previous.price:
                structure_sequence.append(StructureType.LOWER_HIGH)
            else:
                structure_sequence.append(StructureType.EQUAL_HIGH)
        
        # Analyze lows
        for i in range(1, len(swing_lows)):
            current = swing_lows[i]
            previous = swing_lows[i - 1]
            
            if current.price > previous.price:
                structure_sequence.append(StructureType.HIGHER_LOW)
            elif current.price < previous.price:
                structure_sequence.append(StructureType.LOWER_LOW)
            else:
                structure_sequence.append(StructureType.EQUAL_LOW)
        
        return structure_sequence
    
    def determine_trend(self, structure_sequence: List[StructureType]) -> TrendDirection:
        """
        Determine overall trend from structure sequence
        Bullish: Higher highs and higher lows
        Bearish: Lower highs and lower lows
        """
        if not structure_sequence:
            return TrendDirection.NEUTRAL
        
        recent_structure = structure_sequence[-5:]  # Look at recent 5 structure points
        
        bullish_count = sum(1 for s in recent_structure 
                          if s in [StructureType.HIGHER_HIGH, StructureType.HIGHER_LOW])
        bearish_count = sum(1 for s in recent_structure 
                          if s in [StructureType.LOWER_HIGH, StructureType.LOWER_LOW])
        
        if bullish_count > bearish_count * 1.5:
            return TrendDirection.BULLISH
        elif bearish_count > bullish_count * 1.5:
            return TrendDirection.BEARISH
        else:
            return TrendDirection.NEUTRAL
    
    def detect_structure_break(self, df: pd.DataFrame, swing_highs: List[SwingPoint],
                               swing_lows: List[SwingPoint]) -> Optional[StructureBreak]:
        """
        Detect if recent price action broke market structure
        """
        if len(df) < 2:
            return None
        
        current_price = df.iloc[-1]['close']
        current_high = df.iloc[-1]['high']
        current_low = df.iloc[-1]['low']
        
        # Check for bullish structure break (breaking above previous high)
        if swing_highs:
            recent_high = max(swing_highs[-3:], key=lambda x: x.price) if len(swing_highs) >= 3 else swing_highs[-1]
            if current_high > recent_high.price:
                return StructureBreak(
                    index=len(df) - 1,
                    break_type=StructureType.HIGHER_HIGH,
                    previous_structure_price=recent_high.price,
                    break_price=current_high,
                    confirmed=False
                )
        
        # Check for bearish structure break (breaking below previous low)
        if swing_lows:
            recent_low = min(swing_lows[-3:], key=lambda x: x.price) if len(swing_lows) >= 3 else swing_lows[-1]
            if current_low < recent_low.price:
                return StructureBreak(
                    index=len(df) - 1,
                    break_type=StructureType.LOWER_LOW,
                    previous_structure_price=recent_low.price,
                    break_price=current_low,
                    confirmed=False
                )
        
        return None
    
    def confirm_structure_break(self, df: pd.DataFrame, structure_break: StructureBreak,
                               confirmation_candles: int = 1) -> bool:
        """
        Confirm structure break with additional candles closing beyond the break
        """
        if structure_break.confirmed:
            return True
        
        break_index = structure_break.index
        current_index = len(df) - 1
        
        if current_index - break_index < confirmation_candles:
            return False
        
        # Check confirmation candles
        if structure_break.break_type == StructureType.HIGHER_HIGH:
            # For bullish break, need closes above previous structure
            for i in range(break_index + 1, break_index + confirmation_candles + 1):
                if i >= len(df):
                    return False
                if df.iloc[i]['close'] <= structure_break.previous_structure_price:
                    return False
            structure_break.confirmed = True
            return True
        
        elif structure_break.break_type == StructureType.LOWER_LOW:
            # For bearish break, need closes below previous structure
            for i in range(break_index + 1, break_index + confirmation_candles + 1):
                if i >= len(df):
                    return False
                if df.iloc[i]['close'] >= structure_break.previous_structure_price:
                    return False
            structure_break.confirmed = True
            return True
        
        return False


class TrendAnalyzer:
    """Analyze trend using multiple timeframes and EMAs"""
    
    def __init__(self, config):
        self.config = config
    
    def get_htf_trend(self, df: pd.DataFrame, ema_fast: pd.Series, 
                      ema_slow: pd.Series) -> TrendDirection:
        """
        Get higher timeframe trend based on EMA positioning
        Bullish: Price > EMA_fast > EMA_slow
        Bearish: Price < EMA_fast < EMA_slow
        """
        if len(df) < 2 or len(ema_fast) < 2 or len(ema_slow) < 2:
            return TrendDirection.NEUTRAL
        
        current_price = df.iloc[-1]['close']
        current_ema_fast = ema_fast.iloc[-1]
        current_ema_slow = ema_slow.iloc[-1]
        
        # Strong bullish trend
        if current_price > current_ema_fast > current_ema_slow:
            return TrendDirection.BULLISH
        
        # Strong bearish trend
        if current_price < current_ema_fast < current_ema_slow:
            return TrendDirection.BEARISH
        
        return TrendDirection.NEUTRAL
    
    def check_trend_alignment(self, htf_trend: TrendDirection, 
                             structure_trend: TrendDirection) -> bool:
        """
        Check if higher timeframe trend aligns with structure trend
        Both should be in same direction for strongest setup
        """
        if htf_trend == TrendDirection.NEUTRAL or structure_trend == TrendDirection.NEUTRAL:
            return False
        
        return htf_trend == structure_trend
    
    def get_trend_strength(self, df: pd.DataFrame, ema_20: pd.Series,
                          ema_50: pd.Series, ema_200: pd.Series) -> float:
        """
        Calculate trend strength based on EMA separation
        Returns value between 0 (no trend) and 1 (strong trend)
        """
        if len(ema_20) < 1 or len(ema_50) < 1 or len(ema_200) < 1:
            return 0.0
        
        current_price = df.iloc[-1]['close']
        
        # Calculate separation percentages
        sep_20_50 = abs(ema_20.iloc[-1] - ema_50.iloc[-1]) / current_price
        sep_50_200 = abs(ema_50.iloc[-1] - ema_200.iloc[-1]) / current_price
        
        # Normalize to 0-1 scale (assume 2% separation is strong)
        strength = min(1.0, (sep_20_50 + sep_50_200) / 0.02)
        
        return strength
    
    def check_price_distance_from_ma(self, current_price: float, 
                                     ma_value: float, atr: float,
                                     max_distance: float = 2.0) -> bool:
        """
        Check if price is within acceptable distance from moving average
        Returns True if within max_distance * ATR
        """
        distance = abs(current_price - ma_value)
        max_allowed = atr * max_distance
        
        return distance <= max_allowed
    
    def detect_ma_crossover(self, ema_fast: pd.Series, ema_slow: pd.Series) -> Optional[str]:
        """
        Detect EMA crossover
        Returns 'bullish', 'bearish', or None
        """
        if len(ema_fast) < 2 or len(ema_slow) < 2:
            return None
        
        # Bullish crossover: fast crosses above slow
        if (ema_fast.iloc[-2] <= ema_slow.iloc[-2] and 
            ema_fast.iloc[-1] > ema_slow.iloc[-1]):
            return 'bullish'
        
        # Bearish crossover: fast crosses below slow
        if (ema_fast.iloc[-2] >= ema_slow.iloc[-2] and 
            ema_fast.iloc[-1] < ema_slow.iloc[-1]):
            return 'bearish'
        
        return None
