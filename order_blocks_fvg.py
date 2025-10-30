"""
Order Blocks (OB) and Fair Value Gaps (FVG) Detection Module
Implements ICT order block and FVG identification
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class OrderBlockType(Enum):
    """Type of order block"""
    BULLISH = "bullish"
    BEARISH = "bearish"


class FVGType(Enum):
    """Type of Fair Value Gap"""
    BULLISH = "bullish"   # Gap up
    BEARISH = "bearish"   # Gap down


@dataclass
class OrderBlock:
    """Represents an ICT Order Block"""
    index: int
    ob_type: OrderBlockType
    high: float
    low: float
    open: float
    close: float
    displacement_pct: float
    body_size_pct: float
    mitigated: bool = False
    mitigation_index: Optional[int] = None
    timestamp: pd.Timestamp = None


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap"""
    index: int
    fvg_type: FVGType
    gap_high: float
    gap_low: float
    gap_size_pips: float
    filled: bool = False
    fill_index: Optional[int] = None
    timestamp: pd.Timestamp = None


class OrderBlockAnalyzer:
    """
    Identifies Order Blocks (OB) based on ICT methodology
    
    An Order Block is the last opposite candle before a strong displacement move:
    - Bullish OB: Last bearish candle before bullish displacement
    - Bearish OB: Last bullish candle before bearish displacement
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.lookback = config.get('ob_lookback', 50)
        self.min_displacement_pct = config.get('ob_min_displacement_pct', 0.15)
        self.min_body_pct = config.get('ob_body_size_min_pct', 30)
        self.pip_value = 0.01  # For XAUUSD
    
    def identify_order_blocks(self, df: pd.DataFrame) -> List[OrderBlock]:
        """
        Identify order blocks in the price data
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            List of OrderBlock objects
        """
        order_blocks = []
        
        for i in range(1, len(df) - 1):
            # Check for bullish displacement (potential bullish OB before it)
            bullish_ob = self._check_bullish_order_block(df, i)
            if bullish_ob:
                order_blocks.append(bullish_ob)
            
            # Check for bearish displacement (potential bearish OB before it)
            bearish_ob = self._check_bearish_order_block(df, i)
            if bearish_ob:
                order_blocks.append(bearish_ob)
        
        return order_blocks
    
    def _check_bullish_order_block(self, df: pd.DataFrame, 
                                   displacement_idx: int) -> Optional[OrderBlock]:
        """
        Check for bullish order block before bullish displacement
        
        Args:
            df: DataFrame with OHLC data
            displacement_idx: Index of potential displacement candle
            
        Returns:
            OrderBlock object if found, None otherwise
        """
        if displacement_idx < 2:
            return None
        
        current_bar = df.iloc[displacement_idx]
        prev_bar = df.iloc[displacement_idx - 1]
        
        # Check for bullish displacement
        displacement_pct = ((current_bar['close'] - current_bar['open']) / 
                           current_bar['open']) * 100
        
        if displacement_pct < self.min_displacement_pct:
            return None
        
        # The OB is the last bearish/down candle before displacement
        # Look back for the last bearish candle
        for j in range(displacement_idx - 1, max(0, displacement_idx - 10), -1):
            check_bar = df.iloc[j]
            
            # Check if bearish candle
            if check_bar['close'] < check_bar['open']:
                # Calculate body size percentage
                candle_range = check_bar['high'] - check_bar['low']
                body_size = abs(check_bar['close'] - check_bar['open'])
                
                if candle_range > 0:
                    body_pct = (body_size / candle_range) * 100
                else:
                    continue
                
                # Validate body size
                if body_pct >= self.min_body_pct:
                    return OrderBlock(
                        index=j,
                        ob_type=OrderBlockType.BULLISH,
                        high=check_bar['high'],
                        low=check_bar['low'],
                        open=check_bar['open'],
                        close=check_bar['close'],
                        displacement_pct=displacement_pct,
                        body_size_pct=body_pct,
                        timestamp=df.index[j]
                    )
                break
        
        return None
    
    def _check_bearish_order_block(self, df: pd.DataFrame, 
                                   displacement_idx: int) -> Optional[OrderBlock]:
        """
        Check for bearish order block before bearish displacement
        
        Args:
            df: DataFrame with OHLC data
            displacement_idx: Index of potential displacement candle
            
        Returns:
            OrderBlock object if found, None otherwise
        """
        if displacement_idx < 2:
            return None
        
        current_bar = df.iloc[displacement_idx]
        
        # Check for bearish displacement
        displacement_pct = ((current_bar['open'] - current_bar['close']) / 
                           current_bar['open']) * 100
        
        if displacement_pct < self.min_displacement_pct:
            return None
        
        # The OB is the last bullish/up candle before displacement
        # Look back for the last bullish candle
        for j in range(displacement_idx - 1, max(0, displacement_idx - 10), -1):
            check_bar = df.iloc[j]
            
            # Check if bullish candle
            if check_bar['close'] > check_bar['open']:
                # Calculate body size percentage
                candle_range = check_bar['high'] - check_bar['low']
                body_size = abs(check_bar['close'] - check_bar['open'])
                
                if candle_range > 0:
                    body_pct = (body_size / candle_range) * 100
                else:
                    continue
                
                # Validate body size
                if body_pct >= self.min_body_pct:
                    return OrderBlock(
                        index=j,
                        ob_type=OrderBlockType.BEARISH,
                        high=check_bar['high'],
                        low=check_bar['low'],
                        open=check_bar['open'],
                        close=check_bar['close'],
                        displacement_pct=displacement_pct,
                        body_size_pct=body_pct,
                        timestamp=df.index[j]
                    )
                break
        
        return None
    
    def check_ob_mitigation(self, df: pd.DataFrame, 
                           order_blocks: List[OrderBlock]) -> List[OrderBlock]:
        """
        Check if order blocks have been mitigated (price returned to OB)
        
        Args:
            df: DataFrame with OHLC data
            order_blocks: List of order blocks to check
            
        Returns:
            Updated list of order blocks with mitigation status
        """
        for ob in order_blocks:
            if ob.mitigated:
                continue
            
            # Check bars after OB creation
            for i in range(ob.index + 1, len(df)):
                current_bar = df.iloc[i]
                
                if ob.ob_type == OrderBlockType.BULLISH:
                    # Check if price returned to bullish OB
                    if current_bar['low'] <= ob.high and current_bar['low'] >= ob.low:
                        ob.mitigated = True
                        ob.mitigation_index = i
                        break
                
                elif ob.ob_type == OrderBlockType.BEARISH:
                    # Check if price returned to bearish OB
                    if current_bar['high'] >= ob.low and current_bar['high'] <= ob.high:
                        ob.mitigated = True
                        ob.mitigation_index = i
                        break
        
        return order_blocks


class FVGAnalyzer:
    """
    Identifies Fair Value Gaps (FVG) based on ICT methodology
    
    A Fair Value Gap occurs when:
    - There's a gap between candle 1's high and candle 3's low (bullish FVG)
    - There's a gap between candle 1's low and candle 3's high (bearish FVG)
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.min_gap_pips = config.get('fvg_min_gap_pips', 5)
        self.lookback = config.get('fvg_lookback', 50)
        self.pip_value = 0.01  # For XAUUSD
        self.min_gap = self.min_gap_pips * self.pip_value
    
    def identify_fvgs(self, df: pd.DataFrame) -> List[FairValueGap]:
        """
        Identify Fair Value Gaps in price data
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            List of FairValueGap objects
        """
        fvgs = []
        
        for i in range(2, len(df)):
            bar1 = df.iloc[i - 2]
            bar2 = df.iloc[i - 1]
            bar3 = df.iloc[i]
            
            # Check for bullish FVG (gap up)
            # Gap exists when bar1's high < bar3's low
            if bar1['high'] < bar3['low']:
                gap_size = (bar3['low'] - bar1['high']) / self.pip_value
                
                if gap_size >= self.min_gap_pips:
                    fvgs.append(FairValueGap(
                        index=i,
                        fvg_type=FVGType.BULLISH,
                        gap_high=bar3['low'],
                        gap_low=bar1['high'],
                        gap_size_pips=gap_size,
                        timestamp=df.index[i]
                    ))
            
            # Check for bearish FVG (gap down)
            # Gap exists when bar1's low > bar3's high
            elif bar1['low'] > bar3['high']:
                gap_size = (bar1['low'] - bar3['high']) / self.pip_value
                
                if gap_size >= self.min_gap_pips:
                    fvgs.append(FairValueGap(
                        index=i,
                        fvg_type=FVGType.BEARISH,
                        gap_high=bar1['low'],
                        gap_low=bar3['high'],
                        gap_size_pips=gap_size,
                        timestamp=df.index[i]
                    ))
        
        return fvgs
    
    def check_fvg_fill(self, df: pd.DataFrame, 
                      fvgs: List[FairValueGap]) -> List[FairValueGap]:
        """
        Check if FVGs have been filled (price returned to gap)
        
        Args:
            df: DataFrame with OHLC data
            fvgs: List of FVGs to check
            
        Returns:
            Updated list of FVGs with fill status
        """
        for fvg in fvgs:
            if fvg.filled:
                continue
            
            # Check bars after FVG creation
            for i in range(fvg.index + 1, len(df)):
                current_bar = df.iloc[i]
                
                # Check if price entered the FVG zone
                if (current_bar['low'] <= fvg.gap_high and 
                    current_bar['high'] >= fvg.gap_low):
                    fvg.filled = True
                    fvg.fill_index = i
                    break
        
        return fvgs
    
    def get_active_fvgs(self, fvgs: List[FairValueGap]) -> List[FairValueGap]:
        """
        Get FVGs that haven't been filled yet
        
        Args:
            fvgs: List of all FVGs
            
        Returns:
            List of unfilled FVGs
        """
        return [fvg for fvg in fvgs if not fvg.filled]
