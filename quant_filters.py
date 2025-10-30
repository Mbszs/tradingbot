"""
Quantitative Filters Module
Implements technical and quantitative filters for trade validation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from scipy import stats


@dataclass
class FilterResult:
    """Result of a filter check"""
    passed: bool
    value: float
    threshold: float
    message: str


class QuantitativeFilters:
    """
    Implements various quantitative filters:
    - ATR (Average True Range) volatility filter
    - Volume filter
    - Correlation filter
    - Trend filter (Linear Regression / Kalman)
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        # ATR settings
        self.atr_period = config.get('atr_period', 14)
        self.atr_min_mult = config.get('atr_min_multiplier', 0.8)
        self.atr_max_mult = config.get('atr_max_multiplier', 2.0)
        self.atr_lookback = config.get('atr_lookback', 100)
        
        # Volume settings
        self.volume_period = config.get('volume_period', 20)
        self.volume_min_mult = config.get('volume_min_multiplier', 1.0)
        
        # Trend filter settings
        self.trend_type = config.get('trend_filter_type', 'linear_regression')
        self.trend_period = config.get('trend_period', 20)
        self.trend_threshold = config.get('trend_strength_threshold', 0.3)
    
    def calculate_atr(self, df: pd.DataFrame, period: Optional[int] = None) -> pd.Series:
        """
        Calculate Average True Range (ATR)
        
        Args:
            df: DataFrame with OHLC data
            period: ATR period (uses config default if None)
            
        Returns:
            Series with ATR values
        """
        if period is None:
            period = self.atr_period
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range calculation
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Average True Range
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def atr_filter(self, df: pd.DataFrame, current_idx: int) -> FilterResult:
        """
        Check if ATR is within acceptable range
        
        Skip trade if:
        - ATR < average (no momentum)
        - ATR > 2x average (possible news event)
        
        Args:
            df: DataFrame with OHLC data
            current_idx: Current bar index
            
        Returns:
            FilterResult object
        """
        atr = self.calculate_atr(df)
        
        # Get current ATR
        current_atr = atr.iloc[current_idx]
        
        # Calculate average ATR over lookback period
        start_idx = max(0, current_idx - self.atr_lookback)
        avg_atr = atr.iloc[start_idx:current_idx].mean()
        
        # Check bounds
        min_atr = avg_atr * self.atr_min_mult
        max_atr = avg_atr * self.atr_max_mult
        
        if current_atr < min_atr:
            return FilterResult(
                passed=False,
                value=current_atr,
                threshold=min_atr,
                message=f"ATR too low: {current_atr:.2f} < {min_atr:.2f}"
            )
        
        if current_atr > max_atr:
            return FilterResult(
                passed=False,
                value=current_atr,
                threshold=max_atr,
                message=f"ATR too high: {current_atr:.2f} > {max_atr:.2f}"
            )
        
        return FilterResult(
            passed=True,
            value=current_atr,
            threshold=avg_atr,
            message=f"ATR valid: {current_atr:.2f} (avg: {avg_atr:.2f})"
        )
    
    def volume_filter(self, df: pd.DataFrame, current_idx: int) -> FilterResult:
        """
        Check if volume is above average (institutional activity)
        
        Args:
            df: DataFrame with OHLC and volume data
            current_idx: Current bar index
            
        Returns:
            FilterResult object
        """
        if 'volume' not in df.columns:
            # If volume data not available, pass filter
            return FilterResult(
                passed=True,
                value=0,
                threshold=0,
                message="Volume data not available"
            )
        
        volume = df['volume']
        
        # Get current volume
        current_volume = volume.iloc[current_idx]
        
        # Calculate rolling mean
        start_idx = max(0, current_idx - self.volume_period)
        avg_volume = volume.iloc[start_idx:current_idx].mean()
        
        threshold = avg_volume * self.volume_min_mult
        
        if current_volume < threshold:
            return FilterResult(
                passed=False,
                value=current_volume,
                threshold=threshold,
                message=f"Volume too low: {current_volume:.0f} < {threshold:.0f}"
            )
        
        return FilterResult(
            passed=True,
            value=current_volume,
            threshold=threshold,
            message=f"Volume valid: {current_volume:.0f} (avg: {avg_volume:.0f})"
        )
    
    def linear_regression_trend(self, df: pd.DataFrame, 
                               current_idx: int,
                               period: Optional[int] = None) -> Dict:
        """
        Calculate trend using linear regression
        
        Args:
            df: DataFrame with OHLC data
            current_idx: Current bar index
            period: Lookback period (uses config default if None)
            
        Returns:
            Dictionary with trend analysis
        """
        if period is None:
            period = self.trend_period
        
        start_idx = max(0, current_idx - period)
        prices = df['close'].iloc[start_idx:current_idx + 1].values
        
        if len(prices) < 2:
            return {
                'slope': 0,
                'r_squared': 0,
                'direction': 'neutral',
                'strength': 0
            }
        
        # Linear regression
        x = np.arange(len(prices))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, prices)
        
        # Normalize slope by price
        normalized_slope = (slope / prices[-1]) * 100
        
        # Determine direction
        if normalized_slope > self.trend_threshold:
            direction = 'bullish'
        elif normalized_slope < -self.trend_threshold:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        return {
            'slope': normalized_slope,
            'r_squared': r_value ** 2,
            'direction': direction,
            'strength': abs(normalized_slope)
        }
    
    def trend_filter(self, df: pd.DataFrame, 
                    current_idx: int,
                    expected_direction: str) -> FilterResult:
        """
        Check if trend aligns with expected direction
        
        Args:
            df: DataFrame with OHLC data
            current_idx: Current bar index
            expected_direction: 'bullish', 'bearish', or 'neutral'
            
        Returns:
            FilterResult object
        """
        trend_info = self.linear_regression_trend(df, current_idx)
        
        direction = trend_info['direction']
        strength = trend_info['strength']
        
        # Check alignment
        if expected_direction != 'neutral' and direction != expected_direction:
            return FilterResult(
                passed=False,
                value=strength,
                threshold=self.trend_threshold,
                message=f"Trend mismatch: {direction} (expected: {expected_direction})"
            )
        
        return FilterResult(
            passed=True,
            value=strength,
            threshold=self.trend_threshold,
            message=f"Trend aligned: {direction} (strength: {strength:.2f})"
        )
    
    def correlation_filter(self, df_primary: pd.DataFrame,
                          df_secondary: pd.DataFrame,
                          current_idx: int,
                          expected_correlation: str = 'inverse') -> FilterResult:
        """
        Check correlation between two instruments (e.g., XAUUSD vs DXY)
        
        Args:
            df_primary: Primary instrument DataFrame
            df_secondary: Secondary instrument DataFrame
            current_idx: Current bar index
            expected_correlation: 'inverse' or 'direct'
            
        Returns:
            FilterResult object
        """
        period = 50  # Correlation lookback period
        
        start_idx = max(0, current_idx - period)
        
        # Get close prices
        primary_prices = df_primary['close'].iloc[start_idx:current_idx + 1]
        secondary_prices = df_secondary['close'].iloc[start_idx:current_idx + 1]
        
        # Ensure same length
        min_len = min(len(primary_prices), len(secondary_prices))
        primary_prices = primary_prices.iloc[-min_len:]
        secondary_prices = secondary_prices.iloc[-min_len:]
        
        if len(primary_prices) < 10:
            return FilterResult(
                passed=True,
                value=0,
                threshold=0,
                message="Insufficient data for correlation"
            )
        
        # Calculate correlation
        correlation = primary_prices.corr(secondary_prices)
        
        # Check if correlation matches expectation
        if expected_correlation == 'inverse' and correlation > -0.5:
            return FilterResult(
                passed=False,
                value=correlation,
                threshold=-0.5,
                message=f"Correlation not inverse: {correlation:.2f}"
            )
        
        if expected_correlation == 'direct' and correlation < 0.5:
            return FilterResult(
                passed=False,
                value=correlation,
                threshold=0.5,
                message=f"Correlation not direct: {correlation:.2f}"
            )
        
        return FilterResult(
            passed=True,
            value=correlation,
            threshold=0.5,
            message=f"Correlation valid: {correlation:.2f}"
        )
    
    def apply_all_filters(self, df: pd.DataFrame, 
                         current_idx: int,
                         expected_direction: str = 'neutral') -> Dict:
        """
        Apply all quantitative filters
        
        Args:
            df: DataFrame with OHLC data
            current_idx: Current bar index
            expected_direction: Expected trend direction
            
        Returns:
            Dictionary with all filter results
        """
        results = {
            'atr': self.atr_filter(df, current_idx),
            'volume': self.volume_filter(df, current_idx),
            'trend': self.trend_filter(df, current_idx, expected_direction)
        }
        
        # Overall pass/fail
        all_passed = all(r.passed for r in results.values())
        
        return {
            'filters': results,
            'all_passed': all_passed,
            'num_passed': sum(1 for r in results.values() if r.passed),
            'num_total': len(results)
        }
