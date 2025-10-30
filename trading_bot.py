"""
ICT XAUUSD Automated Trading Bot
Main entry point for the trading system
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path

# Import custom modules
from config import *
from market_structure import MarketStructureAnalyzer, Bias, StructureType
from liquidity import LiquidityAnalyzer, LiquidityType
from order_blocks_fvg import OrderBlockAnalyzer, FVGAnalyzer, OrderBlockType, FVGType
from fibonacci_ote import FibonacciOTE
from session_filter import SessionFilter, TradingSession
from quant_filters import QuantitativeFilters
from risk_management import RiskManager, TradeDirection, Trade


class ICTTradingBot:
    """
    Main trading bot that integrates all ICT concepts and executes trades
    """
    
    def __init__(self, config_dict: Optional[Dict] = None):
        """
        Initialize the trading bot
        
        Args:
            config_dict: Optional configuration dictionary (uses config.py if None)
        """
        # Setup logging
        self._setup_logging()
        
        # Load configuration
        if config_dict:
            self.config = config_dict
        else:
            self.config = self._load_default_config()
        
        # Initialize components
        self.logger.info("Initializing ICT Trading Bot components...")
        
        self.market_structure = MarketStructureAnalyzer(ICT_CONFIG)
        self.liquidity_analyzer = LiquidityAnalyzer(ICT_CONFIG)
        self.ob_analyzer = OrderBlockAnalyzer(ICT_CONFIG)
        self.fvg_analyzer = FVGAnalyzer(ICT_CONFIG)
        self.fibonacci = FibonacciOTE(ICT_CONFIG)
        self.session_filter = SessionFilter(SESSIONS)
        self.quant_filters = QuantitativeFilters(QUANT_FILTERS)
        self.risk_manager = RiskManager(RISK_CONFIG)
        
        # Trading state
        self.is_running = False
        self.current_bias = Bias.NEUTRAL
        self.htf_bias = Bias.NEUTRAL  # Higher timeframe bias
        
        self.logger.info("ICT Trading Bot initialized successfully")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/trading_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _load_default_config(self) -> Dict:
        """Load default configuration from config.py"""
        return {
            'symbol': SYMBOL,
            'timeframes': TIMEFRAMES,
            'sessions': SESSIONS,
            'risk': RISK_CONFIG,
            'ict': ICT_CONFIG,
            'quant': QUANT_FILTERS,
            'entry_confluence': ENTRY_CONFLUENCE
        }
    
    def analyze_market(self, df_daily: pd.DataFrame, 
                      df_4h: pd.DataFrame,
                      df_1h: pd.DataFrame,
                      df_m15: pd.DataFrame) -> Dict:
        """
        Comprehensive market analysis across multiple timeframes
        
        Args:
            df_daily: Daily timeframe data
            df_4h: 4-hour timeframe data
            df_1h: 1-hour timeframe data
            df_m15: 15-minute timeframe data
            
        Returns:
            Dictionary with complete market analysis
        """
        self.logger.info("Performing multi-timeframe market analysis...")
        
        # Higher timeframe bias (Daily & 4H)
        daily_structure = self.market_structure.get_structure_summary(df_daily)
        h4_structure = self.market_structure.get_structure_summary(df_4h)
        
        # Determine HTF bias
        self.htf_bias = daily_structure['bias']
        
        # Current timeframe analysis (1H for entry)
        h1_structure = self.market_structure.get_structure_summary(df_1h)
        self.current_bias = h1_structure['bias']
        
        # Check bias alignment
        bias_aligned = self.market_structure.is_bias_aligned(
            self.current_bias, self.htf_bias
        )
        
        # Liquidity analysis
        liquidity_summary = self.liquidity_analyzer.get_liquidity_summary(df_1h)
        
        # Order blocks and FVGs
        order_blocks = self.ob_analyzer.identify_order_blocks(df_1h)
        order_blocks = self.ob_analyzer.check_ob_mitigation(df_1h, order_blocks)
        
        fvgs = self.fvg_analyzer.identify_fvgs(df_1h)
        fvgs = self.fvg_analyzer.check_fvg_fill(df_1h, fvgs)
        
        # Get active (unmitigated) OBs and FVGs
        active_obs = [ob for ob in order_blocks if not ob.mitigated]
        active_fvgs = self.fvg_analyzer.get_active_fvgs(fvgs)
        
        # Fibonacci OTE analysis
        fib_summary = self.fibonacci.get_fib_summary(df_1h)
        
        # Compile analysis
        analysis = {
            'timestamp': df_1h.index[-1],
            'htf_bias': self.htf_bias,
            'current_bias': self.current_bias,
            'bias_aligned': bias_aligned,
            'daily_structure': daily_structure,
            'h4_structure': h4_structure,
            'h1_structure': h1_structure,
            'liquidity': liquidity_summary,
            'active_order_blocks': active_obs,
            'active_fvgs': active_fvgs,
            'fibonacci': fib_summary,
            'current_price': df_1h.iloc[-1]['close']
        }
        
        return analysis
    
    def check_entry_conditions(self, analysis: Dict, 
                              df_1h: pd.DataFrame,
                              df_m5: pd.DataFrame) -> Optional[Dict]:
        """
        Check if all entry conditions are met
        
        Args:
            analysis: Market analysis dictionary
            df_1h: 1-hour data
            df_m5: 5-minute data for entry confirmation
            
        Returns:
            Entry signal dictionary if conditions met, None otherwise
        """
        self.logger.info("Checking entry conditions...")
        
        # Get current timestamp and check session
        current_time = df_1h.index[-1]
        current_session = self.session_filter.get_current_session(current_time)
        
        # Check if trading is allowed in this session
        if not self.session_filter.is_trading_allowed(current_time):
            self.logger.info(f"Trading not allowed in {current_session.value} session")
            return None
        
        # Check session trade limit
        if not self.risk_manager.can_open_session_trade(current_session.value):
            self.logger.info(f"Max trades reached for {current_session.value} session")
            return None
        
        # Check if bias is aligned
        if not analysis['bias_aligned']:
            self.logger.info("Bias not aligned between HTF and current TF")
            return None
        
        # Must have a directional bias (not neutral)
        if analysis['current_bias'] == Bias.NEUTRAL:
            self.logger.info("No clear directional bias")
            return None
        
        # Check for recent liquidity sweep
        recent_sweep = analysis['liquidity']['recent_sweep']
        if not recent_sweep:
            self.logger.info("No recent liquidity sweep detected")
            return None
        
        # Check for MSS or CHOCH confirmation
        last_shift = analysis['h1_structure']['last_shift']
        if not last_shift:
            self.logger.info("No recent structure shift detected")
            return None
        
        # Check if structure shift aligns with bias
        expected_direction = (Bias.BULLISH if recent_sweep.pool.liquidity_type == LiquidityType.SELL_SIDE
                            else Bias.BEARISH)
        
        if last_shift.direction != expected_direction:
            self.logger.info("Structure shift doesn't align with liquidity sweep")
            return None
        
        # Check for valid OB or FVG for entry
        current_price = analysis['current_price']
        valid_entry_zone = False
        entry_ob = None
        entry_fvg = None
        
        # Check Order Blocks
        for ob in analysis['active_order_blocks']:
            if expected_direction == Bias.BULLISH:
                if ob.ob_type == OrderBlockType.BULLISH:
                    if ob.low <= current_price <= ob.high:
                        valid_entry_zone = True
                        entry_ob = ob
                        break
            else:
                if ob.ob_type == OrderBlockType.BEARISH:
                    if ob.low <= current_price <= ob.high:
                        valid_entry_zone = True
                        entry_ob = ob
                        break
        
        # Check FVGs if no valid OB
        if not valid_entry_zone:
            for fvg in analysis['active_fvgs']:
                if expected_direction == Bias.BULLISH:
                    if fvg.fvg_type == FVGType.BULLISH:
                        if fvg.gap_low <= current_price <= fvg.gap_high:
                            valid_entry_zone = True
                            entry_fvg = fvg
                            break
                else:
                    if fvg.fvg_type == FVGType.BEARISH:
                        if fvg.gap_low <= current_price <= fvg.gap_high:
                            valid_entry_zone = True
                            entry_fvg = fvg
                            break
        
        if not valid_entry_zone:
            self.logger.info("Price not in valid entry zone (OB or FVG)")
            return None
        
        # Apply quantitative filters
        current_idx = len(df_1h) - 1
        filter_results = self.quant_filters.apply_all_filters(
            df_1h, current_idx, expected_direction.value
        )
        
        if not filter_results['all_passed']:
            self.logger.info(f"Quant filters failed: {filter_results}")
            return None
        
        # Check OTE zone (optional confluence)
        in_ote = analysis['fibonacci']['in_ote_zone']
        
        # Count confluences
        confluences = []
        if recent_sweep:
            confluences.append('liquidity_sweep')
        if last_shift:
            confluences.append('structure_shift')
        if entry_ob or entry_fvg:
            confluences.append('ob_or_fvg')
        if in_ote:
            confluences.append('ote_zone')
        if filter_results['filters']['volume'].passed:
            confluences.append('volume_spike')
        if filter_results['filters']['atr'].passed:
            confluences.append('atr_valid')
        if filter_results['filters']['trend'].passed:
            confluences.append('trend_aligned')
        
        required_confluences = ENTRY_CONFLUENCE['required_confluences']
        
        if len(confluences) < required_confluences:
            self.logger.info(f"Insufficient confluences: {len(confluences)}/{required_confluences}")
            return None
        
        # All conditions met - generate entry signal
        self.logger.info(f"✅ Entry conditions met! Confluences: {confluences}")
        
        # Calculate stop loss and take profit
        if expected_direction == Bias.BULLISH:
            # For long: stop below OB/FVG or recent swing low
            if entry_ob:
                stop_loss = entry_ob.low - (10 * 0.01)  # 10 pips buffer
            elif entry_fvg:
                stop_loss = entry_fvg.gap_low - (10 * 0.01)
            else:
                stop_loss = recent_sweep.sweep_price - (15 * 0.01)
            
            # Take profit at opposite liquidity or next FVG
            take_profit = None
            for pool in analysis['liquidity']['buy_side_pools']:
                if pool.price_level > current_price:
                    take_profit = pool.price_level
                    break
            
            if not take_profit:
                # Default to 2R
                take_profit = current_price + (abs(current_price - stop_loss) * 2)
        
        else:  # Bearish
            # For short: stop above OB/FVG or recent swing high
            if entry_ob:
                stop_loss = entry_ob.high + (10 * 0.01)
            elif entry_fvg:
                stop_loss = entry_fvg.gap_high + (10 * 0.01)
            else:
                stop_loss = recent_sweep.sweep_price + (15 * 0.01)
            
            # Take profit at opposite liquidity or next FVG
            take_profit = None
            for pool in analysis['liquidity']['sell_side_pools']:
                if pool.price_level < current_price:
                    take_profit = pool.price_level
                    break
            
            if not take_profit:
                # Default to 2R
                take_profit = current_price - (abs(stop_loss - current_price) * 2)
        
        return {
            'direction': expected_direction,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'confluences': confluences,
            'session': current_session.value,
            'timestamp': current_time,
            'entry_ob': entry_ob,
            'entry_fvg': entry_fvg,
            'liquidity_sweep': recent_sweep
        }
    
    def execute_trade(self, entry_signal: Dict) -> Optional[Trade]:
        """
        Execute a trade based on entry signal
        
        Args:
            entry_signal: Entry signal dictionary
            
        Returns:
            Trade object if successful, None otherwise
        """
        self.logger.info(f"Executing trade: {entry_signal['direction'].value}")
        
        # Map bias to trade direction
        if entry_signal['direction'] == Bias.BULLISH:
            direction = TradeDirection.LONG
        else:
            direction = TradeDirection.SHORT
        
        # Create trade
        trade = self.risk_manager.create_trade(
            symbol=SYMBOL,
            direction=direction,
            entry_price=entry_signal['entry_price'],
            stop_loss=entry_signal['stop_loss'],
            take_profit=entry_signal['take_profit'],
            metadata={
                'confluences': entry_signal['confluences'],
                'session': entry_signal['session'],
                'entry_reason': 'ICT Setup'
            }
        )
        
        if not trade:
            self.logger.warning("Failed to create trade (risk checks failed)")
            return None
        
        # Open trade
        if self.risk_manager.open_trade(trade):
            self.logger.info(f"✅ Trade opened: {trade.trade_id}")
            self.logger.info(f"   Entry: {trade.entry_price:.2f}")
            self.logger.info(f"   Stop Loss: {trade.stop_loss:.2f}")
            self.logger.info(f"   Take Profit: {trade.take_profit:.2f}")
            self.logger.info(f"   Position Size: {trade.position_size:.2f} lots")
            self.logger.info(f"   Risk: ${trade.risk_amount:.2f} ({trade.risk_pct:.1f}%)")
            
            # Register session trade
            self.risk_manager.register_session_trade(entry_signal['session'])
            
            return trade
        
        return None
    
    def run_strategy(self, data: Dict[str, pd.DataFrame]) -> None:
        """
        Main strategy execution loop
        
        Args:
            data: Dictionary of timeframe data
                  {'daily': df, '4h': df, '1h': df, '15m': df, '5m': df}
        """
        self.logger.info("=" * 80)
        self.logger.info("Starting ICT XAUUSD Trading Strategy")
        self.logger.info("=" * 80)
        
        self.is_running = True
        
        try:
            # Perform market analysis
            analysis = self.analyze_market(
                data['daily'],
                data['4h'],
                data['1h'],
                data['15m']
            )
            
            self.logger.info(f"Market Analysis Complete:")
            self.logger.info(f"  HTF Bias: {analysis['htf_bias'].value}")
            self.logger.info(f"  Current Bias: {analysis['current_bias'].value}")
            self.logger.info(f"  Bias Aligned: {analysis['bias_aligned']}")
            self.logger.info(f"  Active OBs: {len(analysis['active_order_blocks'])}")
            self.logger.info(f"  Active FVGs: {len(analysis['active_fvgs'])}")
            
            # Manage existing trades
            for trade in self.risk_manager.open_trades[:]:
                current_price = data['1h'].iloc[-1]['close']
                self.risk_manager.manage_trade(trade, current_price)
            
            # Check for new entry if no open trades
            if len(self.risk_manager.open_trades) == 0:
                entry_signal = self.check_entry_conditions(
                    analysis,
                    data['1h'],
                    data['5m']
                )
                
                if entry_signal:
                    self.execute_trade(entry_signal)
            
            # Display statistics
            stats = self.risk_manager.get_statistics()
            self.logger.info(f"\nTrading Statistics:")
            self.logger.info(f"  Total Trades: {stats.total_trades}")
            self.logger.info(f"  Win Rate: {stats.win_rate:.1f}%")
            self.logger.info(f"  Total P&L: ${stats.total_pnl:.2f} ({stats.total_pnl_pct:.2f}%)")
            self.logger.info(f"  Account Balance: ${self.risk_manager.account_balance:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error in strategy execution: {e}", exc_info=True)
        
        finally:
            self.is_running = False


def main():
    """Main entry point for the trading bot"""
    # Initialize bot
    bot = ICTTradingBot()
    
    # In a real implementation, you would:
    # 1. Connect to broker API
    # 2. Fetch live data
    # 3. Run in a loop with proper timing
    
    # For now, this is a framework - you need to add data fetching
    print("ICT XAUUSD Trading Bot initialized.")
    print("Please integrate with your broker API to fetch live data.")
    print("Example data sources: MetaTrader 5, Oanda, Interactive Brokers, etc.")


if __name__ == "__main__":
    main()
