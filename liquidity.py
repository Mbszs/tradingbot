"""
Liquidity Detection Module
Identifies liquidity pools and sweeps based on ICT concepts
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class LiquidityType(Enum):
    """Type of liquidity"""
    BUY_SIDE = "buy_side"      # Above equal highs
    SELL_SIDE = "sell_side"    # Below equal lows


@dataclass
class LiquidityPool:
    """Represents a liquidity pool (equal highs/lows)"""
    price_level: float
    liquidity_type: LiquidityType
    touches: List[int]  # Indices where price touched this level
    strength: int       # Number of touches
    timestamp: pd.Timestamp
    swept: bool = False
    sweep_timestamp: Optional[pd.Timestamp] = None


@dataclass
class LiquiditySweep:
    """Represents a liquidity sweep event"""
    pool: LiquidityPool
    sweep_index: int
    sweep_price: float
    displacement_strength: float  # How strong was the reversal
    timestamp: pd.Timestamp


class LiquidityAnalyzer:
    """
    Identifies and tracks liquidity pools and sweeps
    
    Key Concepts:
    - Equal highs = buy-side liquidity (stops above)
    - Equal lows = sell-side liquidity (stops below)
    - Liquidity sweep = price moves beyond level then reverses
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.lookback = config.get('liquidity_lookback', 100)
        self.tolerance_pips = config.get('liquidity_tolerance_pips', 2)
        self.sweep_pips = config.get('liquidity_sweep_pips', 3)
        
        # Convert pips to price (for XAUUSD, 1 pip = 0.01)
        self.pip_value = 0.01
        self.tolerance = self.tolerance_pips * self.pip_value
        self.sweep_threshold = self.sweep_pips * self.pip_value
    
    def identify_equal_highs(self, df: pd.DataFrame, 
                            min_touches: int = 2) -> List[LiquidityPool]:
        """
        Identify equal highs (buy-side liquidity)
        
        Args:
            df: DataFrame with OHLC data
            min_touches: Minimum number of touches to confirm level
            
        Returns:
            List of LiquidityPool objects for equal highs
        """
        pools = []
        highs = df['high'].values
        
        # Group similar highs
        levels = {}
        
        for i in range(len(df)):
            high = highs[i]
            
            # Check if this high is close to any existing level
            matched = False
            for level_price in list(levels.keys()):
                if abs(high - level_price) <= self.tolerance:
                    levels[level_price].append(i)
                    matched = True
                    break
            
            if not matched:
                levels[high] = [i]
        
        # Create liquidity pools for levels with multiple touches
        for price_level, touches in levels.items():
            if len(touches) >= min_touches:
                pools.append(LiquidityPool(
                    price_level=price_level,
                    liquidity_type=LiquidityType.BUY_SIDE,
                    touches=touches,
                    strength=len(touches),
                    timestamp=df.index[touches[-1]]
                ))
        
        return pools
    
    def identify_equal_lows(self, df: pd.DataFrame, 
                           min_touches: int = 2) -> List[LiquidityPool]:
        """
        Identify equal lows (sell-side liquidity)
        
        Args:
            df: DataFrame with OHLC data
            min_touches: Minimum number of touches to confirm level
            
        Returns:
            List of LiquidityPool objects for equal lows
        """
        pools = []
        lows = df['low'].values
        
        # Group similar lows
        levels = {}
        
        for i in range(len(df)):
            low = lows[i]
            
            # Check if this low is close to any existing level
            matched = False
            for level_price in list(levels.keys()):
                if abs(low - level_price) <= self.tolerance:
                    levels[level_price].append(i)
                    matched = True
                    break
            
            if not matched:
                levels[low] = [i]
        
        # Create liquidity pools for levels with multiple touches
        for price_level, touches in levels.items():
            if len(touches) >= min_touches:
                pools.append(LiquidityPool(
                    price_level=price_level,
                    liquidity_type=LiquidityType.SELL_SIDE,
                    touches=touches,
                    strength=len(touches),
                    timestamp=df.index[touches[-1]]
                ))
        
        return pools
    
    def detect_liquidity_sweep(self, df: pd.DataFrame, 
                              pools: List[LiquidityPool]) -> List[LiquiditySweep]:
        """
        Detect liquidity sweeps (stop runs)
        
        A sweep occurs when:
        1. Price moves beyond the liquidity level
        2. Price reverses in the opposite direction (displacement)
        
        Args:
            df: DataFrame with OHLC data
            pools: List of liquidity pools to check
            
        Returns:
            List of LiquiditySweep objects
        """
        sweeps = []
        
        for pool in pools:
            if pool.swept:
                continue
            
            # Get the last touch index
            last_touch_idx = max(pool.touches)
            
            # Check bars after last touch
            for i in range(last_touch_idx + 1, len(df)):
                current_bar = df.iloc[i]
                
                if pool.liquidity_type == LiquidityType.BUY_SIDE:
                    # Check for sweep above high
                    if current_bar['high'] > pool.price_level + self.sweep_threshold:
                        # Check for displacement (reversal)
                        displacement = self._check_bearish_displacement(df, i)
                        
                        if displacement > 0:
                            pool.swept = True
                            pool.sweep_timestamp = df.index[i]
                            
                            sweeps.append(LiquiditySweep(
                                pool=pool,
                                sweep_index=i,
                                sweep_price=current_bar['high'],
                                displacement_strength=displacement,
                                timestamp=df.index[i]
                            ))
                            break
                
                elif pool.liquidity_type == LiquidityType.SELL_SIDE:
                    # Check for sweep below low
                    if current_bar['low'] < pool.price_level - self.sweep_threshold:
                        # Check for displacement (reversal)
                        displacement = self._check_bullish_displacement(df, i)
                        
                        if displacement > 0:
                            pool.swept = True
                            pool.sweep_timestamp = df.index[i]
                            
                            sweeps.append(LiquiditySweep(
                                pool=pool,
                                sweep_index=i,
                                sweep_price=current_bar['low'],
                                displacement_strength=displacement,
                                timestamp=df.index[i]
                            ))
                            break
        
        return sweeps
    
    def _check_bullish_displacement(self, df: pd.DataFrame, 
                                   start_idx: int, 
                                   lookforward: int = 3) -> float:
        """
        Check for bullish displacement after sweep
        
        Args:
            df: DataFrame with OHLC data
            start_idx: Index where sweep occurred
            lookforward: Bars to look forward
            
        Returns:
            Displacement strength (0 = none, 1+ = strong)
        """
        if start_idx + lookforward >= len(df):
            return 0.0
        
        sweep_low = df.iloc[start_idx]['low']
        
        # Check next bars for strong bullish move
        max_high = df.iloc[start_idx:start_idx + lookforward + 1]['high'].max()
        displacement_pct = ((max_high - sweep_low) / sweep_low) * 100
        
        # Normalize displacement strength
        return displacement_pct / 0.2  # 0.2% move = strength of 1.0
    
    def _check_bearish_displacement(self, df: pd.DataFrame, 
                                   start_idx: int, 
                                   lookforward: int = 3) -> float:
        """
        Check for bearish displacement after sweep
        
        Args:
            df: DataFrame with OHLC data
            start_idx: Index where sweep occurred
            lookforward: Bars to look forward
            
        Returns:
            Displacement strength (0 = none, 1+ = strong)
        """
        if start_idx + lookforward >= len(df):
            return 0.0
        
        sweep_high = df.iloc[start_idx]['high']
        
        # Check next bars for strong bearish move
        min_low = df.iloc[start_idx:start_idx + lookforward + 1]['low'].min()
        displacement_pct = ((sweep_high - min_low) / sweep_high) * 100
        
        # Normalize displacement strength
        return displacement_pct / 0.2  # 0.2% move = strength of 1.0
    
    def get_liquidity_summary(self, df: pd.DataFrame) -> Dict:
        """
        Get comprehensive liquidity analysis
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Dictionary with liquidity analysis results
        """
        buy_side_pools = self.identify_equal_highs(df)
        sell_side_pools = self.identify_equal_lows(df)
        
        all_pools = buy_side_pools + sell_side_pools
        sweeps = self.detect_liquidity_sweep(df, all_pools)
        
        return {
            'buy_side_pools': buy_side_pools,
            'sell_side_pools': sell_side_pools,
            'total_pools': len(all_pools),
            'sweeps': sweeps,
            'recent_sweep': sweeps[-1] if sweeps else None
        }
