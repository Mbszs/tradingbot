"""
ICT (Inner Circle Trader) Concepts Detector
Implements Fair Value Gaps, Order Blocks, and Liquidity Pool detection
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class FairValueGap:
    """Fair Value Gap structure"""
    start_index: int
    end_index: int
    gap_high: float
    gap_low: float
    gap_type: str  # 'bullish' or 'bearish'
    filled_percent: float = 0.0
    is_valid: bool = True


@dataclass
class OrderBlock:
    """Order Block structure"""
    index: int
    high: float
    low: float
    open: float
    close: float
    block_type: str  # 'bullish' or 'bearish'
    strength: float  # 0-1 based on body size and volume
    touches: int = 0
    is_valid: bool = True


@dataclass
class LiquidityPool:
    """Liquidity Pool structure"""
    price_level: float
    pool_type: str  # 'buy_side', 'sell_side', 'equal_highs', 'equal_lows'
    indices: List[int]
    strength: int  # Number of touches/equal levels
    swept: bool = False


class ICTDetector:
    """Detect ICT concepts for trading opportunities"""
    
    def __init__(self, config):
        self.config = config
        self.fvgs: List[FairValueGap] = []
        self.order_blocks: List[OrderBlock] = []
        self.liquidity_pools: List[LiquidityPool] = []
    
    def detect_fair_value_gaps(self, df: pd.DataFrame, atr: float) -> List[FairValueGap]:
        """
        Detect Fair Value Gaps (FVGs)
        A FVG exists when there's a gap between candle[i-1] and candle[i+1]
        that candle[i] doesn't fill
        """
        fvgs = []
        min_gap_size = atr * self.config.FVG_MIN_SIZE
        
        for i in range(2, len(df)):
            # Bullish FVG: gap between candle[i-2].high and candle[i].low
            # with candle[i-1] not filling it
            if (df.iloc[i]['low'] > df.iloc[i-2]['high'] and
                df.iloc[i-1]['low'] > df.iloc[i-2]['high']):
                
                gap_low = df.iloc[i-2]['high']
                gap_high = df.iloc[i]['low']
                gap_size = gap_high - gap_low
                
                if gap_size >= min_gap_size:
                    fvg = FairValueGap(
                        start_index=i-2,
                        end_index=i,
                        gap_high=gap_high,
                        gap_low=gap_low,
                        gap_type='bullish'
                    )
                    fvgs.append(fvg)
            
            # Bearish FVG: gap between candle[i-2].low and candle[i].high
            # with candle[i-1] not filling it
            if (df.iloc[i]['high'] < df.iloc[i-2]['low'] and
                df.iloc[i-1]['high'] < df.iloc[i-2]['low']):
                
                gap_high = df.iloc[i-2]['low']
                gap_low = df.iloc[i]['high']
                gap_size = gap_high - gap_low
                
                if gap_size >= min_gap_size:
                    fvg = FairValueGap(
                        start_index=i-2,
                        end_index=i,
                        gap_high=gap_high,
                        gap_low=gap_low,
                        gap_type='bearish'
                    )
                    fvgs.append(fvg)
        
        return fvgs
    
    def update_fvg_status(self, fvgs: List[FairValueGap], current_price: float):
        """Update FVG fill status based on current price"""
        for fvg in fvgs:
            if not fvg.is_valid:
                continue
            
            gap_size = fvg.gap_high - fvg.gap_low
            
            if fvg.gap_type == 'bullish':
                # Price dipping into FVG
                if current_price <= fvg.gap_high:
                    penetration = fvg.gap_high - current_price
                    fvg.filled_percent = min(1.0, penetration / gap_size)
            else:  # bearish
                # Price rising into FVG
                if current_price >= fvg.gap_low:
                    penetration = current_price - fvg.gap_low
                    fvg.filled_percent = min(1.0, penetration / gap_size)
            
            # Invalidate if filled beyond threshold
            if fvg.filled_percent >= self.config.FVG_FILL_THRESHOLD:
                fvg.is_valid = False
    
    def detect_order_blocks(self, df: pd.DataFrame, lookback: int = 50) -> List[OrderBlock]:
        """
        Detect Order Blocks
        An order block is the last candle before a strong move
        Bullish OB: Last down candle before strong up move
        Bearish OB: Last up candle before strong down move
        """
        order_blocks = []
        
        for i in range(lookback, len(df) - 1):
            candle = df.iloc[i]
            next_candle = df.iloc[i + 1]
            
            # Calculate body size and candle properties
            body_size = abs(candle['close'] - candle['open'])
            candle_range = candle['high'] - candle['low']
            
            if candle_range == 0:
                continue
            
            body_percent = body_size / candle_range
            
            # Bullish Order Block: Down candle followed by strong up move
            if (candle['close'] < candle['open'] and
                next_candle['close'] > next_candle['open'] and
                body_percent >= self.config.OB_MIN_BODY_PERCENT):
                
                # Check for strong move after
                move_strength = (next_candle['close'] - next_candle['open']) / candle_range
                if move_strength > 1.0:  # Move larger than OB candle
                    ob = OrderBlock(
                        index=i,
                        high=candle['high'],
                        low=candle['low'],
                        open=candle['open'],
                        close=candle['close'],
                        block_type='bullish',
                        strength=min(1.0, body_percent * move_strength)
                    )
                    order_blocks.append(ob)
            
            # Bearish Order Block: Up candle followed by strong down move
            if (candle['close'] > candle['open'] and
                next_candle['close'] < next_candle['open'] and
                body_percent >= self.config.OB_MIN_BODY_PERCENT):
                
                # Check for strong move after
                move_strength = (next_candle['open'] - next_candle['close']) / candle_range
                if move_strength > 1.0:  # Move larger than OB candle
                    ob = OrderBlock(
                        index=i,
                        high=candle['high'],
                        low=candle['low'],
                        open=candle['open'],
                        close=candle['close'],
                        block_type='bearish',
                        strength=min(1.0, body_percent * move_strength)
                    )
                    order_blocks.append(ob)
        
        return order_blocks
    
    def update_order_block_status(self, order_blocks: List[OrderBlock], 
                                  current_price: float, current_index: int):
        """Update order block validity and touch count"""
        for ob in order_blocks:
            if not ob.is_valid:
                continue
            
            # Check age
            age = current_index - ob.index
            if age > self.config.OB_MAX_AGE:
                ob.is_valid = False
                continue
            
            # Check if price touched the order block
            if ob.block_type == 'bullish':
                # Price dipping into bullish OB
                if ob.low <= current_price <= ob.high:
                    ob.touches += 1
            else:  # bearish
                # Price rising into bearish OB
                if ob.low <= current_price <= ob.high:
                    ob.touches += 1
            
            # Invalidate if broken through
            if ob.block_type == 'bullish' and current_price < ob.low:
                ob.is_valid = False
            elif ob.block_type == 'bearish' and current_price > ob.high:
                ob.is_valid = False
    
    def detect_liquidity_pools(self, df: pd.DataFrame, lookback: int = 20) -> List[LiquidityPool]:
        """
        Detect Liquidity Pools
        - Buy-side liquidity: Recent swing highs
        - Sell-side liquidity: Recent swing lows
        - Equal highs/lows: Multiple touches at similar levels
        """
        liquidity_pools = []
        tolerance = self.config.EQUAL_LEVEL_TOLERANCE
        
        recent_df = df.iloc[-lookback:]
        
        # Detect swing highs (buy-side liquidity above)
        for i in range(2, len(recent_df) - 2):
            if (recent_df.iloc[i]['high'] > recent_df.iloc[i-1]['high'] and
                recent_df.iloc[i]['high'] > recent_df.iloc[i-2]['high'] and
                recent_df.iloc[i]['high'] > recent_df.iloc[i+1]['high'] and
                recent_df.iloc[i]['high'] > recent_df.iloc[i+2]['high']):
                
                pool = LiquidityPool(
                    price_level=recent_df.iloc[i]['high'],
                    pool_type='buy_side',
                    indices=[len(df) - lookback + i],
                    strength=1
                )
                liquidity_pools.append(pool)
        
        # Detect swing lows (sell-side liquidity below)
        for i in range(2, len(recent_df) - 2):
            if (recent_df.iloc[i]['low'] < recent_df.iloc[i-1]['low'] and
                recent_df.iloc[i]['low'] < recent_df.iloc[i-2]['low'] and
                recent_df.iloc[i]['low'] < recent_df.iloc[i+1]['low'] and
                recent_df.iloc[i]['low'] < recent_df.iloc[i+2]['low']):
                
                pool = LiquidityPool(
                    price_level=recent_df.iloc[i]['low'],
                    pool_type='sell_side',
                    indices=[len(df) - lookback + i],
                    strength=1
                )
                liquidity_pools.append(pool)
        
        # Detect equal highs
        highs = recent_df['high'].values
        for i in range(len(highs) - 1):
            equal_indices = [i]
            for j in range(i + 1, len(highs)):
                if abs(highs[i] - highs[j]) / highs[i] < tolerance:
                    equal_indices.append(j)
            
            if len(equal_indices) >= 2:
                pool = LiquidityPool(
                    price_level=np.mean([highs[idx] for idx in equal_indices]),
                    pool_type='equal_highs',
                    indices=[len(df) - lookback + idx for idx in equal_indices],
                    strength=len(equal_indices)
                )
                liquidity_pools.append(pool)
        
        # Detect equal lows
        lows = recent_df['low'].values
        for i in range(len(lows) - 1):
            equal_indices = [i]
            for j in range(i + 1, len(lows)):
                if abs(lows[i] - lows[j]) / lows[i] < tolerance:
                    equal_indices.append(j)
            
            if len(equal_indices) >= 2:
                pool = LiquidityPool(
                    price_level=np.mean([lows[idx] for idx in equal_indices]),
                    pool_type='equal_lows',
                    indices=[len(df) - lookback + idx for idx in equal_indices],
                    strength=len(equal_indices)
                )
                liquidity_pools.append(pool)
        
        # Remove duplicates (keep strongest)
        unique_pools = {}
        for pool in liquidity_pools:
            key = (pool.pool_type, round(pool.price_level, 2))
            if key not in unique_pools or pool.strength > unique_pools[key].strength:
                unique_pools[key] = pool
        
        return list(unique_pools.values())
    
    def check_liquidity_sweep(self, liquidity_pools: List[LiquidityPool], 
                             current_candle: pd.Series) -> List[LiquidityPool]:
        """Check if current candle swept any liquidity pools"""
        swept_pools = []
        
        for pool in liquidity_pools:
            if pool.swept:
                continue
            
            if pool.pool_type in ['buy_side', 'equal_highs']:
                # Check if price spiked above and rejected
                if current_candle['high'] >= pool.price_level:
                    pool.swept = True
                    swept_pools.append(pool)
            
            elif pool.pool_type in ['sell_side', 'equal_lows']:
                # Check if price spiked below and rejected
                if current_candle['low'] <= pool.price_level:
                    pool.swept = True
                    swept_pools.append(pool)
        
        return swept_pools
    
    def get_nearest_fvg(self, fvgs: List[FairValueGap], current_price: float, 
                       fvg_type: str) -> Optional[FairValueGap]:
        """Get nearest valid FVG of specified type"""
        valid_fvgs = [fvg for fvg in fvgs if fvg.is_valid and fvg.gap_type == fvg_type]
        
        if not valid_fvgs:
            return None
        
        # Find nearest FVG
        nearest = min(valid_fvgs, key=lambda fvg: 
                     abs(((fvg.gap_high + fvg.gap_low) / 2) - current_price))
        return nearest
    
    def get_nearest_order_block(self, order_blocks: List[OrderBlock], 
                                current_price: float, ob_type: str) -> Optional[OrderBlock]:
        """Get nearest valid order block of specified type"""
        valid_obs = [ob for ob in order_blocks if ob.is_valid and ob.block_type == ob_type]
        
        if not valid_obs:
            return None
        
        # Find nearest OB, prefer untouched (fresh) ones
        valid_obs.sort(key=lambda ob: (ob.touches, abs(((ob.high + ob.low) / 2) - current_price)))
        return valid_obs[0]
