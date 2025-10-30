"""
Signal Generator Module
Generates entry and exit signals based on ICT concepts and quantitative filters
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime

from market_structure import TrendDirection, MarketStructure, TrendAnalyzer
from ict_detector import ICTDetector, FairValueGap, OrderBlock, LiquidityPool
from indicators import TechnicalIndicators, PriceActionDetector


@dataclass
class TradingSignal:
    """Trading signal structure"""
    timestamp: datetime
    signal_type: str  # 'long', 'short', 'close_long', 'close_short'
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    confidence: float  # 0-1 score based on confirmations
    reason: str  # Description of why signal was generated
    metadata: Dict  # Additional signal info


class SignalGenerator:
    """Generate trading signals combining ICT and quantitative analysis"""
    
    def __init__(self, config):
        self.config = config
        self.ict_detector = ICTDetector(config)
        self.market_structure = MarketStructure(config)
        self.trend_analyzer = TrendAnalyzer(config)
        self.indicators = TechnicalIndicators()
        self.price_action = PriceActionDetector()
    
    def analyze_market(self, df: pd.DataFrame, df_htf: pd.DataFrame) -> Dict:
        """
        Perform comprehensive market analysis
        Returns dict with all indicators, structure, and ICT concepts
        """
        # Calculate indicators on entry timeframe
        ema_20 = self.indicators.calculate_ema(df['close'], self.config.EMA_20)
        ema_50 = self.indicators.calculate_ema(df['close'], self.config.EMA_FAST)
        ema_200 = self.indicators.calculate_ema(df['close'], self.config.EMA_SLOW)
        
        macd_line, signal_line, histogram = self.indicators.calculate_macd(
            df['close'], self.config.MACD_FAST, self.config.MACD_SLOW, self.config.MACD_SIGNAL
        )
        
        rsi = self.indicators.calculate_rsi(df['close'], self.config.RSI_PERIOD)
        atr = self.indicators.calculate_atr(df['high'], df['low'], df['close'], 
                                           self.config.ATR_PERIOD)
        obv = self.indicators.calculate_obv(df['close'], df['volume'])
        volume_ma = self.indicators.calculate_volume_sma(df['volume'])
        
        # Higher timeframe trend
        htf_ema_fast = self.indicators.calculate_ema(df_htf['close'], self.config.EMA_FAST)
        htf_ema_slow = self.indicators.calculate_ema(df_htf['close'], self.config.EMA_SLOW)
        htf_trend = self.trend_analyzer.get_htf_trend(df_htf, htf_ema_fast, htf_ema_slow)
        
        # Market structure
        swing_highs = self.market_structure.detect_swing_highs(df, self.config.SWING_LOOKBACK)
        swing_lows = self.market_structure.detect_swing_lows(df, self.config.SWING_LOOKBACK)
        structure_sequence = self.market_structure.analyze_structure(swing_highs, swing_lows)
        structure_trend = self.market_structure.determine_trend(structure_sequence)
        
        # ICT concepts
        current_atr = atr.iloc[-1] if len(atr) > 0 else 0
        fvgs = self.ict_detector.detect_fair_value_gaps(df, current_atr)
        order_blocks = self.ict_detector.detect_order_blocks(df, self.config.OB_LOOKBACK)
        liquidity_pools = self.ict_detector.detect_liquidity_pools(df, self.config.LIQUIDITY_LOOKBACK)
        
        # Update ICT status
        current_price = df.iloc[-1]['close']
        self.ict_detector.update_fvg_status(fvgs, current_price)
        self.ict_detector.update_order_block_status(order_blocks, current_price, len(df) - 1)
        swept_liquidity = self.ict_detector.check_liquidity_sweep(liquidity_pools, df.iloc[-1])
        
        return {
            # Indicators
            'ema_20': ema_20,
            'ema_50': ema_50,
            'ema_200': ema_200,
            'macd_line': macd_line,
            'signal_line': signal_line,
            'histogram': histogram,
            'rsi': rsi,
            'atr': atr,
            'obv': obv,
            'volume_ma': volume_ma,
            
            # Trends
            'htf_trend': htf_trend,
            'structure_trend': structure_trend,
            
            # Market structure
            'swing_highs': swing_highs,
            'swing_lows': swing_lows,
            'structure_sequence': structure_sequence,
            
            # ICT
            'fvgs': fvgs,
            'order_blocks': order_blocks,
            'liquidity_pools': liquidity_pools,
            'swept_liquidity': swept_liquidity
        }
    
    def check_session_filter(self, timestamp: datetime) -> bool:
        """Check if current time is within allowed trading sessions"""
        if not self.config.ENABLE_SESSION_FILTER:
            return True
        
        hour = timestamp.hour
        
        # Avoid Asian session if configured
        if self.config.AVOID_ASIAN_SESSION:
            if 0 <= hour < 8:  # Asian session roughly 00:00-08:00 UTC
                return False
        
        # Allow London session
        if self.config.LONDON_OPEN <= hour < self.config.LONDON_CLOSE:
            return True
        
        # Allow NY session
        if self.config.NY_OPEN <= hour < self.config.NY_CLOSE:
            return True
        
        return False
    
    def calculate_confidence(self, confirmations: Dict) -> float:
        """
        Calculate signal confidence based on number of confirmations
        Returns score 0-1
        """
        total_checks = len(confirmations)
        passed_checks = sum(1 for v in confirmations.values() if v)
        
        if total_checks == 0:
            return 0.0
        
        return passed_checks / total_checks
    
    def generate_long_signal(self, df: pd.DataFrame, df_htf: pd.DataFrame,
                            analysis: Dict) -> Optional[TradingSignal]:
        """
        Generate long entry signal
        Requires: HTF bullish, structure bullish, price at ICT zone, quant confirmations
        """
        current_candle = df.iloc[-1]
        current_price = current_candle['close']
        current_atr = analysis['atr'].iloc[-1]
        
        # Session filter
        if not self.check_session_filter(current_candle.name):
            return None
        
        # Core confirmations
        confirmations = {}
        reasons = []
        
        # 1. Higher timeframe trend must be bullish
        confirmations['htf_bullish'] = analysis['htf_trend'] == TrendDirection.BULLISH
        if confirmations['htf_bullish']:
            reasons.append("HTF bullish trend")
        
        # 2. Market structure bullish or neutral
        confirmations['structure_ok'] = analysis['structure_trend'] in [
            TrendDirection.BULLISH, TrendDirection.NEUTRAL
        ]
        if analysis['structure_trend'] == TrendDirection.BULLISH:
            reasons.append("Bullish market structure")
        
        # 3. Price above 50 EMA
        confirmations['above_ema'] = current_price > analysis['ema_50'].iloc[-1]
        
        # 4. MACD bullish
        macd_signals = self.indicators.detect_macd_crossover(
            analysis['macd_line'], analysis['signal_line'], analysis['histogram'],
            self.config.MACD_HISTOGRAM_EXPANSION
        )
        confirmations['macd_bullish'] = (macd_signals['bullish'] or 
                                        analysis['macd_line'].iloc[-1] > analysis['signal_line'].iloc[-1])
        if macd_signals['bullish']:
            reasons.append("MACD bullish crossover")
        
        # 5. RSI confirmation
        confirmations['rsi_ok'] = analysis['rsi'].iloc[-1] > self.config.RSI_LONG_THRESHOLD
        if confirmations['rsi_ok']:
            reasons.append(f"RSI {analysis['rsi'].iloc[-1]:.1f} > 50")
        
        # 6. ATR filter (avoid low volatility)
        confirmations['atr_ok'] = current_atr > self.config.ATR_MIN_THRESHOLD
        
        # 7. Volume spike
        volume_spike = self.indicators.check_volume_spike(
            df['volume'], analysis['volume_ma'], self.config.MIN_VOLUME_SPIKE
        )
        confirmations['volume_spike'] = volume_spike
        if volume_spike:
            reasons.append("Volume spike detected")
        
        # 8. MA ribbon alignment
        ma_ribbon = self.indicators.check_ma_ribbon_alignment(
            analysis['ema_20'], analysis['ema_50'], analysis['ema_200']
        )
        confirmations['ribbon_aligned'] = ma_ribbon['bullish_aligned']
        if ma_ribbon['bullish_aligned']:
            reasons.append("MA ribbon aligned bullish")
        
        # 9. Price not too far from MA
        confirmations['price_distance_ok'] = self.trend_analyzer.check_price_distance_from_ma(
            current_price, analysis['ema_50'].iloc[-1], current_atr, 
            self.config.MAX_DISTANCE_FROM_MA
        )
        
        # 10. ICT zone confirmation (FVG or Order Block)
        nearest_bullish_fvg = self.ict_detector.get_nearest_fvg(
            analysis['fvgs'], current_price, 'bullish'
        )
        nearest_bullish_ob = self.ict_detector.get_nearest_order_block(
            analysis['order_blocks'], current_price, 'bullish'
        )
        
        at_ict_zone = False
        if nearest_bullish_fvg and nearest_bullish_fvg.gap_low <= current_price <= nearest_bullish_fvg.gap_high:
            at_ict_zone = True
            reasons.append("Price at bullish FVG")
        elif nearest_bullish_ob and nearest_bullish_ob.low <= current_price <= nearest_bullish_ob.high:
            at_ict_zone = True
            reasons.append(f"Price at bullish Order Block (strength {nearest_bullish_ob.strength:.2f})")
        
        confirmations['ict_zone'] = at_ict_zone
        
        # 11. Price action patterns
        bullish_engulfing = self.price_action.is_bullish_engulfing(df)
        hammer = self.price_action.is_hammer(df)
        bullish_pin = self.price_action.is_pin_bar(df, direction='bullish')
        
        price_action_signal = bullish_engulfing or hammer or bullish_pin
        confirmations['price_action'] = price_action_signal
        
        if bullish_engulfing:
            reasons.append("Bullish engulfing pattern")
        elif hammer:
            reasons.append("Hammer pattern")
        elif bullish_pin:
            reasons.append("Bullish pin bar")
        
        # 12. Liquidity sweep (optional but adds conviction)
        liquidity_swept = any(lp.pool_type in ['sell_side', 'equal_lows'] 
                             for lp in analysis['swept_liquidity'])
        if liquidity_swept:
            reasons.append("Sell-side liquidity swept")
            confirmations['liquidity_sweep'] = True
        
        # Calculate confidence
        confidence = self.calculate_confidence(confirmations)
        
        # Minimum required confirmations (adjust threshold as needed)
        required_confirmations = ['htf_bullish', 'structure_ok', 'above_ema', 
                                 'macd_bullish', 'rsi_ok', 'atr_ok']
        
        # Check if all required confirmations pass
        if not all(confirmations.get(key, False) for key in required_confirmations):
            return None
        
        # Need either ICT zone or strong price action
        if not (confirmations.get('ict_zone', False) or 
               (confirmations.get('price_action', False) and confidence > 0.7)):
            return None
        
        # Calculate stop loss and take profits
        stop_loss = current_price - (current_atr * self.config.STOP_LOSS_ATR)
        risk = current_price - stop_loss
        
        take_profit_1 = current_price + (risk * self.config.TAKE_PROFIT_1)
        take_profit_2 = current_price + (risk * self.config.TAKE_PROFIT_2)
        
        # Generate signal
        signal = TradingSignal(
            timestamp=current_candle.name,
            signal_type='long',
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            confidence=confidence,
            reason=' | '.join(reasons),
            metadata={
                'confirmations': confirmations,
                'atr': current_atr,
                'rsi': analysis['rsi'].iloc[-1],
                'ict_zone': at_ict_zone
            }
        )
        
        return signal
    
    def generate_short_signal(self, df: pd.DataFrame, df_htf: pd.DataFrame,
                             analysis: Dict) -> Optional[TradingSignal]:
        """
        Generate short entry signal
        Requires: HTF bearish, structure bearish, price at ICT zone, quant confirmations
        """
        current_candle = df.iloc[-1]
        current_price = current_candle['close']
        current_atr = analysis['atr'].iloc[-1]
        
        # Session filter
        if not self.check_session_filter(current_candle.name):
            return None
        
        # Core confirmations
        confirmations = {}
        reasons = []
        
        # 1. Higher timeframe trend must be bearish
        confirmations['htf_bearish'] = analysis['htf_trend'] == TrendDirection.BEARISH
        if confirmations['htf_bearish']:
            reasons.append("HTF bearish trend")
        
        # 2. Market structure bearish or neutral
        confirmations['structure_ok'] = analysis['structure_trend'] in [
            TrendDirection.BEARISH, TrendDirection.NEUTRAL
        ]
        if analysis['structure_trend'] == TrendDirection.BEARISH:
            reasons.append("Bearish market structure")
        
        # 3. Price below 50 EMA
        confirmations['below_ema'] = current_price < analysis['ema_50'].iloc[-1]
        
        # 4. MACD bearish
        macd_signals = self.indicators.detect_macd_crossover(
            analysis['macd_line'], analysis['signal_line'], analysis['histogram'],
            self.config.MACD_HISTOGRAM_EXPANSION
        )
        confirmations['macd_bearish'] = (macd_signals['bearish'] or 
                                        analysis['macd_line'].iloc[-1] < analysis['signal_line'].iloc[-1])
        if macd_signals['bearish']:
            reasons.append("MACD bearish crossover")
        
        # 5. RSI confirmation
        confirmations['rsi_ok'] = analysis['rsi'].iloc[-1] < self.config.RSI_SHORT_THRESHOLD
        if confirmations['rsi_ok']:
            reasons.append(f"RSI {analysis['rsi'].iloc[-1]:.1f} < 50")
        
        # 6. ATR filter
        confirmations['atr_ok'] = current_atr > self.config.ATR_MIN_THRESHOLD
        
        # 7. Volume spike
        volume_spike = self.indicators.check_volume_spike(
            df['volume'], analysis['volume_ma'], self.config.MIN_VOLUME_SPIKE
        )
        confirmations['volume_spike'] = volume_spike
        if volume_spike:
            reasons.append("Volume spike detected")
        
        # 8. MA ribbon alignment
        ma_ribbon = self.indicators.check_ma_ribbon_alignment(
            analysis['ema_20'], analysis['ema_50'], analysis['ema_200']
        )
        confirmations['ribbon_aligned'] = ma_ribbon['bearish_aligned']
        if ma_ribbon['bearish_aligned']:
            reasons.append("MA ribbon aligned bearish")
        
        # 9. Price not too far from MA
        confirmations['price_distance_ok'] = self.trend_analyzer.check_price_distance_from_ma(
            current_price, analysis['ema_50'].iloc[-1], current_atr,
            self.config.MAX_DISTANCE_FROM_MA
        )
        
        # 10. ICT zone confirmation
        nearest_bearish_fvg = self.ict_detector.get_nearest_fvg(
            analysis['fvgs'], current_price, 'bearish'
        )
        nearest_bearish_ob = self.ict_detector.get_nearest_order_block(
            analysis['order_blocks'], current_price, 'bearish'
        )
        
        at_ict_zone = False
        if nearest_bearish_fvg and nearest_bearish_fvg.gap_low <= current_price <= nearest_bearish_fvg.gap_high:
            at_ict_zone = True
            reasons.append("Price at bearish FVG")
        elif nearest_bearish_ob and nearest_bearish_ob.low <= current_price <= nearest_bearish_ob.high:
            at_ict_zone = True
            reasons.append(f"Price at bearish Order Block (strength {nearest_bearish_ob.strength:.2f})")
        
        confirmations['ict_zone'] = at_ict_zone
        
        # 11. Price action patterns
        bearish_engulfing = self.price_action.is_bearish_engulfing(df)
        shooting_star = self.price_action.is_shooting_star(df)
        bearish_pin = self.price_action.is_pin_bar(df, direction='bearish')
        
        price_action_signal = bearish_engulfing or shooting_star or bearish_pin
        confirmations['price_action'] = price_action_signal
        
        if bearish_engulfing:
            reasons.append("Bearish engulfing pattern")
        elif shooting_star:
            reasons.append("Shooting star pattern")
        elif bearish_pin:
            reasons.append("Bearish pin bar")
        
        # 12. Liquidity sweep
        liquidity_swept = any(lp.pool_type in ['buy_side', 'equal_highs'] 
                             for lp in analysis['swept_liquidity'])
        if liquidity_swept:
            reasons.append("Buy-side liquidity swept")
            confirmations['liquidity_sweep'] = True
        
        # Calculate confidence
        confidence = self.calculate_confidence(confirmations)
        
        # Minimum required confirmations
        required_confirmations = ['htf_bearish', 'structure_ok', 'below_ema',
                                 'macd_bearish', 'rsi_ok', 'atr_ok']
        
        if not all(confirmations.get(key, False) for key in required_confirmations):
            return None
        
        # Need either ICT zone or strong price action
        if not (confirmations.get('ict_zone', False) or 
               (confirmations.get('price_action', False) and confidence > 0.7)):
            return None
        
        # Calculate stop loss and take profits
        stop_loss = current_price + (current_atr * self.config.STOP_LOSS_ATR)
        risk = stop_loss - current_price
        
        take_profit_1 = current_price - (risk * self.config.TAKE_PROFIT_1)
        take_profit_2 = current_price - (risk * self.config.TAKE_PROFIT_2)
        
        # Generate signal
        signal = TradingSignal(
            timestamp=current_candle.name,
            signal_type='short',
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            confidence=confidence,
            reason=' | '.join(reasons),
            metadata={
                'confirmations': confirmations,
                'atr': current_atr,
                'rsi': analysis['rsi'].iloc[-1],
                'ict_zone': at_ict_zone
            }
        )
        
        return signal
    
    def generate_signal(self, df: pd.DataFrame, df_htf: pd.DataFrame) -> Optional[TradingSignal]:
        """
        Generate trading signal (long or short)
        Returns the highest confidence signal
        """
        # Perform market analysis
        analysis = self.analyze_market(df, df_htf)
        
        # Try to generate both signals
        long_signal = self.generate_long_signal(df, df_htf, analysis)
        short_signal = self.generate_short_signal(df, df_htf, analysis)
        
        # Return highest confidence signal
        if long_signal and short_signal:
            return long_signal if long_signal.confidence > short_signal.confidence else short_signal
        elif long_signal:
            return long_signal
        elif short_signal:
            return short_signal
        
        return None
