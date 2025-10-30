"""
Market Structure Analysis Module
Implements ICT Smart Money Concepts for structure identification
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class Bias(Enum):
    """Market bias enumeration"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class StructureType(Enum):
    """Structure shift types"""
    MSS = "Market Structure Shift"  # Break of structure in trend direction
    CHOCH = "Change of Character"   # Break counter to current trend


@dataclass
class SwingPoint:
    """Represents a swing high or swing low"""
    index: int
    price: float
    is_high: bool  # True for swing high, False for swing low
    timestamp: pd.Timestamp


@dataclass
class StructureShift:
    """Represents a MSS or CHOCH"""
    type: StructureType
    direction: Bias
    break_point: SwingPoint
    timestamp: pd.Timestamp
    strength: float  # 0-1 indicating strength of break


class MarketStructureAnalyzer:
    """
    Analyzes market structure to identify:
    - Swing highs and lows
    - Market Structure Shifts (MSS)
    - Change of Character (CHOCH)
    - Overall market bias
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.lookback = config.get('structure_lookback', 50)
        self.min_move_pct = config.get('structure_min_move_pct', 0.1)
        
    def identify_swing_points(self, df: pd.DataFrame, 
                            left_bars: int = 5, 
                            right_bars: int = 5) -> List[SwingPoint]:
        """
        Identify swing highs and swing lows
        
        Args:
            df: DataFrame with OHLC data
            left_bars: Number of bars to the left for comparison
            right_bars: Number of bars to the right for comparison
            
        Returns:
            List of SwingPoint objects
        """
        swing_points = []
        
        highs = df['high'].values
        lows = df['low'].values
        
        for i in range(left_bars, len(df) - right_bars):
            # Check for swing high
            is_swing_high = True
            for j in range(i - left_bars, i + right_bars + 1):
                if j != i and highs[j] >= highs[i]:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_points.append(SwingPoint(
                    index=i,
                    price=highs[i],
                    is_high=True,
                    timestamp=df.index[i]
                ))
            
            # Check for swing low
            is_swing_low = True
            for j in range(i - left_bars, i + right_bars + 1):
                if j != i and lows[j] <= lows[i]:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_points.append(SwingPoint(
                    index=i,
                    price=lows[i],
                    is_high=False,
                    timestamp=df.index[i]
                ))
        
        return sorted(swing_points, key=lambda x: x.index)
    
    def detect_structure_shift(self, df: pd.DataFrame, 
                              swing_points: List[SwingPoint]) -> List[StructureShift]:
        """
        Detect Market Structure Shifts (MSS) and Change of Character (CHOCH)
        
        MSS: Break of structure in the direction of the trend
        CHOCH: Break of structure counter to the current trend (potential reversal)
        
        Args:
            df: DataFrame with OHLC data
            swing_points: List of identified swing points
            
        Returns:
            List of StructureShift objects
        """
        shifts = []
        
        if len(swing_points) < 4:
            return shifts
        
        # Separate swing highs and lows
        swing_highs = [sp for sp in swing_points if sp.is_high]
        swing_lows = [sp for sp in swing_points if not sp.is_high]
        
        # Determine current trend
        current_bias = self.determine_bias(df, swing_points)
        
        # Check for breaks of structure
        for i in range(len(df)):
            current_price = df.iloc[i]['close']
            current_high = df.iloc[i]['high']
            current_low = df.iloc[i]['low']
            
            # Check for bullish structure shift (break above previous high)
            for sh in swing_highs:
                if sh.index < i and current_high > sh.price:
                    # Calculate strength of break
                    move_pct = ((current_high - sh.price) / sh.price) * 100
                    
                    if move_pct >= self.min_move_pct:
                        # Determine if MSS or CHOCH
                        if current_bias == Bias.BULLISH:
                            shift_type = StructureType.MSS
                        else:
                            shift_type = StructureType.CHOCH
                        
                        shifts.append(StructureShift(
                            type=shift_type,
                            direction=Bias.BULLISH,
                            break_point=sh,
                            timestamp=df.index[i],
                            strength=min(move_pct / 1.0, 1.0)  # Normalize to 0-1
                        ))
                        break
            
            # Check for bearish structure shift (break below previous low)
            for sl in swing_lows:
                if sl.index < i and current_low < sl.price:
                    # Calculate strength of break
                    move_pct = ((sl.price - current_low) / sl.price) * 100
                    
                    if move_pct >= self.min_move_pct:
                        # Determine if MSS or CHOCH
                        if current_bias == Bias.BEARISH:
                            shift_type = StructureType.MSS
                        else:
                            shift_type = StructureType.CHOCH
                        
                        shifts.append(StructureShift(
                            type=shift_type,
                            direction=Bias.BEARISH,
                            break_point=sl,
                            timestamp=df.index[i],
                            strength=min(move_pct / 1.0, 1.0)
                        ))
                        break
        
        return shifts
    
    def determine_bias(self, df: pd.DataFrame, 
                      swing_points: List[SwingPoint] = None,
                      timeframe: str = 'H4') -> Bias:
        """
        Determine overall market bias based on structure
        
        Rules:
        - Bullish: Higher highs and higher lows
        - Bearish: Lower highs and lower lows
        - Neutral: Ranging or unclear structure
        
        Args:
            df: DataFrame with OHLC data
            swing_points: Pre-identified swing points (optional)
            timeframe: Timeframe being analyzed
            
        Returns:
            Bias enum (BULLISH, BEARISH, or NEUTRAL)
        """
        if swing_points is None:
            swing_points = self.identify_swing_points(df)
        
        if len(swing_points) < 4:
            return Bias.NEUTRAL
        
        # Get recent swing points
        recent_points = swing_points[-6:]
        swing_highs = [sp for sp in recent_points if sp.is_high]
        swing_lows = [sp for sp in recent_points if not sp.is_high]
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return Bias.NEUTRAL
        
        # Check for higher highs and higher lows (bullish)
        higher_highs = all(swing_highs[i].price < swing_highs[i+1].price 
                          for i in range(len(swing_highs)-1))
        higher_lows = all(swing_lows[i].price < swing_lows[i+1].price 
                         for i in range(len(swing_lows)-1))
        
        # Check for lower highs and lower lows (bearish)
        lower_highs = all(swing_highs[i].price > swing_highs[i+1].price 
                         for i in range(len(swing_highs)-1))
        lower_lows = all(swing_lows[i].price > swing_lows[i+1].price 
                        for i in range(len(swing_lows)-1))
        
        if higher_highs and higher_lows:
            return Bias.BULLISH
        elif lower_highs and lower_lows:
            return Bias.BEARISH
        else:
            return Bias.NEUTRAL
    
    def is_bias_aligned(self, current_tf_bias: Bias, higher_tf_bias: Bias) -> bool:
        """
        Check if current timeframe bias aligns with higher timeframe
        
        Args:
            current_tf_bias: Bias on current timeframe
            higher_tf_bias: Bias on higher timeframe (e.g., Daily, 4H)
            
        Returns:
            True if aligned, False otherwise
        """
        if higher_tf_bias == Bias.NEUTRAL:
            return True  # No conflict
        
        return current_tf_bias == higher_tf_bias
    
    def get_structure_summary(self, df: pd.DataFrame) -> Dict:
        """
        Get comprehensive structure analysis summary
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Dictionary with structure analysis results
        """
        swing_points = self.identify_swing_points(df)
        structure_shifts = self.detect_structure_shift(df, swing_points)
        bias = self.determine_bias(df, swing_points)
        
        return {
            'bias': bias,
            'swing_points': swing_points,
            'structure_shifts': structure_shifts,
            'last_shift': structure_shifts[-1] if structure_shifts else None,
            'num_swing_highs': len([sp for sp in swing_points if sp.is_high]),
            'num_swing_lows': len([sp for sp in swing_points if not sp.is_high])
        }
