"""
XAU/USD Trading Bot for MetaTrader 5
MT5-specific implementation with full integration
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
import time

from config import TradingConfig
from signal_generator import SignalGenerator, TradingSignal
from risk_manager import RiskManager, Position
from indicators import TechnicalIndicators
from mt5_connector import MT5Connector


class XAUUSDTradingBotMT5:
    """
    MetaTrader 5 Trading Bot
    Fully integrated with MT5 for automated trading
    """
    
    def __init__(self, config: TradingConfig, mt5_connector: MT5Connector = None,
                 live_mode: bool = False):
        """
        Initialize MT5 trading bot
        
        Args:
            config: Trading configuration
            mt5_connector: MT5Connector instance (will create if None)
            live_mode: If True, execute real trades
        """
        self.config = config
        self.live_mode = live_mode
        self.signal_generator = SignalGenerator(config)
        self.indicators = TechnicalIndicators()
        
        # MT5 connector
        if mt5_connector is None:
            self.mt5 = MT5Connector(symbol=config.SYMBOL)
        else:
            self.mt5 = mt5_connector
        
        # Initialize risk manager with account balance
        account_info = self.mt5.get_account_info()
        initial_capital = account_info.get('balance', 10000)
        self.risk_manager = RiskManager(config, initial_capital)
        
        # Setup logging
        self.setup_logging()
        
        # Data storage
        self.data_1h: Optional[pd.DataFrame] = None
        self.data_4h: Optional[pd.DataFrame] = None
        self.data_daily: Optional[pd.DataFrame] = None
        
        # Position tracking (MT5 ticket to our Position object)
        self.mt5_positions: Dict[int, Position] = {}
        
        # State
        self.last_update: Optional[datetime] = None
        self.is_running = False
        
        self.logger.info(f"MT5 Trading Bot Initialized - Mode: {'LIVE' if live_mode else 'PAPER'}")
        self.logger.info(f"Account Balance: ${initial_capital:,.2f}")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        if self.config.ENABLE_LOGGING:
            logging.basicConfig(
                level=getattr(logging, self.config.LOG_LEVEL),
                format=log_format,
                handlers=[
                    logging.FileHandler(f"{self.config.LOG_PATH}trading_bot_mt5.log"),
                    logging.StreamHandler()
                ]
            )
        else:
            logging.basicConfig(level=logging.INFO, format=log_format)
        
        self.logger = logging.getLogger(__name__)
    
    def update_data(self):
        """Update market data from MT5"""
        try:
            self.logger.debug("Updating market data from MT5...")
            
            # Load data for each timeframe
            self.data_1h = self.mt5.get_historical_data(
                self.config.TIMEFRAME_ENTRY, bars=1000
            )
            self.data_4h = self.mt5.get_historical_data(
                self.config.TIMEFRAME_STRUCTURE, bars=500
            )
            self.data_daily = self.mt5.get_historical_data(
                self.config.TIMEFRAME_HTF, bars=250
            )
            
            self.last_update = datetime.now()
            self.logger.debug("Market data updated successfully")
            
            if self.data_1h.empty or self.data_4h.empty or self.data_daily.empty:
                self.logger.warning("One or more timeframes returned empty data")
            
        except Exception as e:
            self.logger.error(f"Error updating market data: {e}")
            raise
    
    def sync_positions_from_mt5(self):
        """Sync positions from MT5 to our risk manager"""
        try:
            mt5_positions = self.mt5.get_open_positions()
            
            # Update our tracking
            for mt5_pos in mt5_positions:
                ticket = mt5_pos['ticket']
                
                # If we don't have this position, it might be from before bot started
                # or manually opened - we'll track it but won't manage it
                if ticket not in self.mt5_positions:
                    self.logger.info(f"Found existing MT5 position {ticket} - now tracking")
                    
                    # Create Position object for tracking
                    position = Position(
                        entry_time=mt5_pos['time'],
                        position_type=mt5_pos['type'],
                        entry_price=mt5_pos['price_open'],
                        size=mt5_pos['volume'],
                        stop_loss=mt5_pos['sl'],
                        take_profit_1=mt5_pos['tp'],
                        take_profit_2=mt5_pos['tp'],
                        remaining_size=mt5_pos['volume']
                    )
                    
                    self.mt5_positions[ticket] = position
            
            # Remove positions that no longer exist in MT5
            existing_tickets = {pos['ticket'] for pos in mt5_positions}
            closed_tickets = set(self.mt5_positions.keys()) - existing_tickets
            
            for ticket in closed_tickets:
                self.logger.info(f"Position {ticket} closed in MT5")
                del self.mt5_positions[ticket]
            
        except Exception as e:
            self.logger.error(f"Error syncing positions: {e}")
    
    def check_trading_conditions(self) -> Dict[str, bool]:
        """Check if all conditions are met for trading"""
        conditions = {
            'mt5_connected': self.mt5.connected,
            'data_loaded': all([
                self.data_1h is not None and not self.data_1h.empty,
                self.data_4h is not None and not self.data_4h.empty,
                self.data_daily is not None and not self.data_daily.empty
            ]),
            'sufficient_data': False,
            'can_trade': False
        }
        
        if not conditions['mt5_connected']:
            conditions['reason'] = 'MT5 not connected'
            return conditions
        
        if conditions['data_loaded']:
            min_data = max(self.config.EMA_SLOW, self.config.OB_LOOKBACK) + 50
            conditions['sufficient_data'] = len(self.data_1h) >= min_data
        
        if conditions['sufficient_data']:
            can_trade_check = self.risk_manager.can_open_position(datetime.now())
            conditions['can_trade'] = can_trade_check['can_trade']
            conditions['trade_check_reason'] = can_trade_check['reason']
        
        return conditions
    
    def process_signal(self, signal: TradingSignal) -> bool:
        """
        Process trading signal and execute with MT5
        
        Returns True if position was opened
        """
        if not signal:
            return False
        
        current_time = datetime.now()
        
        # Calculate ATR for position sizing
        atr_series = self.indicators.calculate_atr(
            self.data_1h['high'], self.data_1h['low'], self.data_1h['close'],
            self.config.ATR_PERIOD
        )
        current_atr = atr_series.iloc[-1] if len(atr_series) > 0 else 1.0
        
        # Check if we can open position (risk management)
        can_trade = self.risk_manager.can_open_position(current_time)
        if not can_trade['can_trade']:
            self.logger.warning(f"Cannot open position: {can_trade['reason']}")
            return False
        
        # Calculate position size in USD risk
        risk_percent = min(self.config.RISK_PER_TRADE, self.config.MAX_RISK_PER_TRADE)
        if signal.confidence < 0.7:
            risk_percent *= 0.7
        
        account = self.mt5.get_account_info()
        risk_amount = account['balance'] * risk_percent
        
        # Calculate lot size using MT5
        stop_loss_points = abs(signal.entry_price - signal.stop_loss) / self.mt5.get_symbol_info()['point']
        lot_size = self.mt5.calculate_lot_size(risk_amount, stop_loss_points)
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"OPENING {signal.signal_type.upper()} POSITION")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Entry Price:    ${signal.entry_price:.2f}")
        self.logger.info(f"Stop Loss:      ${signal.stop_loss:.2f}")
        self.logger.info(f"Take Profit 1:  ${signal.take_profit_1:.2f}")
        self.logger.info(f"Take Profit 2:  ${signal.take_profit_2:.2f}")
        self.logger.info(f"Lot Size:       {lot_size:.2f}")
        self.logger.info(f"Risk Amount:    ${risk_amount:.2f}")
        self.logger.info(f"Confidence:     {signal.confidence:.1%}")
        self.logger.info(f"Reason:         {signal.reason}")
        self.logger.info(f"{'='*60}\n")
        
        # Execute trade with MT5 (if live mode)
        if self.live_mode:
            # Open position via MT5
            ticket = self.mt5.open_position(
                position_type=signal.signal_type,
                volume=lot_size,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit_1,  # Set TP1 initially
                comment=f"Bot: {signal.confidence:.0%} conf"
            )
            
            if ticket:
                # Create our position tracking object
                position = Position(
                    entry_time=current_time,
                    position_type=signal.signal_type,
                    entry_price=signal.entry_price,
                    size=lot_size,
                    stop_loss=signal.stop_loss,
                    take_profit_1=signal.take_profit_1,
                    take_profit_2=signal.take_profit_2,
                    remaining_size=lot_size
                )
                
                self.mt5_positions[ticket] = position
                self.risk_manager.positions.append(position)
                
                self.logger.info(f"Position opened successfully - Ticket: {ticket}")
                return True
            else:
                self.logger.error("Failed to open position in MT5")
                return False
        else:
            # Paper trading - just track internally
            position = self.risk_manager.open_position(signal, current_time, current_atr)
            if position:
                self.logger.info("Position opened (PAPER TRADING)")
                return True
        
        return False
    
    def update_positions(self):
        """Update all open positions"""
        if not self.data_1h or len(self.data_1h) == 0:
            return
        
        current_time = datetime.now()
        current_price = self.data_1h.iloc[-1]['close']
        
        # Calculate ATR
        atr_series = self.indicators.calculate_atr(
            self.data_1h['high'], self.data_1h['low'], self.data_1h['close'],
            self.config.ATR_PERIOD
        )
        current_atr = atr_series.iloc[-1] if len(atr_series) > 0 else 1.0
        
        if self.live_mode:
            # Sync with MT5 first
            self.sync_positions_from_mt5()
            
            # Update each tracked position
            for ticket, position in list(self.mt5_positions.items()):
                # Get current MT5 position info
                mt5_positions = self.mt5.get_open_positions()
                mt5_pos = next((p for p in mt5_positions if p['ticket'] == ticket), None)
                
                if mt5_pos is None:
                    # Position closed in MT5
                    self.logger.info(f"Position {ticket} closed externally")
                    del self.mt5_positions[ticket]
                    if position in self.risk_manager.positions:
                        self.risk_manager.positions.remove(position)
                    continue
                
                # Update position with current price
                current_price = mt5_pos['price_current']
                
                # Check for TP1 hit (partial close)
                should_partial_close = False
                if not position.tp1_hit:
                    if position.position_type == 'long' and current_price >= position.take_profit_1:
                        should_partial_close = True
                        position.tp1_hit = True
                    elif position.position_type == 'short' and current_price <= position.take_profit_1:
                        should_partial_close = True
                        position.tp1_hit = True
                
                if should_partial_close:
                    close_volume = position.size * self.config.TAKE_PROFIT_1_SIZE
                    if self.mt5.partial_close(ticket, close_volume):
                        self.logger.info(f"TP1 hit - Partially closed {close_volume:.2f} lots")
                        position.remaining_size -= close_volume
                        
                        # Move stop loss to breakeven
                        self.mt5.modify_position(ticket, stop_loss=position.entry_price)
                        self.logger.info(f"Moved SL to breakeven: {position.entry_price:.2f}")
                
                # Check for TP2 hit (another partial close)
                if not position.tp2_hit and position.tp1_hit:
                    should_partial_close_2 = False
                    if position.position_type == 'long' and current_price >= position.take_profit_2:
                        should_partial_close_2 = True
                        position.tp2_hit = True
                    elif position.position_type == 'short' and current_price <= position.take_profit_2:
                        should_partial_close_2 = True
                        position.tp2_hit = True
                    
                    if should_partial_close_2:
                        close_volume = position.size * self.config.TAKE_PROFIT_2_SIZE
                        if self.mt5.partial_close(ticket, close_volume):
                            self.logger.info(f"TP2 hit - Partially closed {close_volume:.2f} lots")
                            position.remaining_size -= close_volume
                
                # Activate trailing stop at 2R
                if not position.trailing_stop_active and position.tp1_hit:
                    risk = abs(position.entry_price - position.stop_loss)
                    
                    if position.position_type == 'long':
                        profit = current_price - position.entry_price
                        r_multiple = profit / risk if risk > 0 else 0
                        
                        if r_multiple >= self.config.TRAILING_STOP_ACTIVATION:
                            position.trailing_stop_active = True
                            new_sl = current_price - (current_atr * self.config.TRAILING_STOP_ATR)
                            self.mt5.modify_position(ticket, stop_loss=new_sl)
                            position.trailing_stop_price = new_sl
                            self.logger.info(f"Trailing stop activated at {new_sl:.2f}")
                    else:
                        profit = position.entry_price - current_price
                        r_multiple = profit / risk if risk > 0 else 0
                        
                        if r_multiple >= self.config.TRAILING_STOP_ACTIVATION:
                            position.trailing_stop_active = True
                            new_sl = current_price + (current_atr * self.config.TRAILING_STOP_ATR)
                            self.mt5.modify_position(ticket, stop_loss=new_sl)
                            position.trailing_stop_price = new_sl
                            self.logger.info(f"Trailing stop activated at {new_sl:.2f}")
                
                # Update trailing stop
                if position.trailing_stop_active:
                    if position.position_type == 'long':
                        new_trailing = current_price - (current_atr * self.config.TRAILING_STOP_ATR)
                        if new_trailing > position.trailing_stop_price:
                            self.mt5.modify_position(ticket, stop_loss=new_trailing)
                            position.trailing_stop_price = new_trailing
                            self.logger.info(f"Trailing stop updated to {new_trailing:.2f}")
                    else:
                        new_trailing = current_price + (current_atr * self.config.TRAILING_STOP_ATR)
                        if new_trailing < position.trailing_stop_price:
                            self.mt5.modify_position(ticket, stop_loss=new_trailing)
                            position.trailing_stop_price = new_trailing
                            self.logger.info(f"Trailing stop updated to {new_trailing:.2f}")
        else:
            # Paper trading - use internal risk manager
            for position in self.risk_manager.positions[:]:
                closed_trades = self.risk_manager.update_position(
                    position, current_price, current_time, current_atr
                )
                
                for trade in closed_trades:
                    self.logger.info(f"\n{'='*60}")
                    self.logger.info(f"POSITION CLOSED (PAPER): {trade.position_type.upper()}")
                    self.logger.info(f"{'='*60}")
                    self.logger.info(f"Entry:  ${trade.entry_price:.2f}")
                    self.logger.info(f"Exit:   ${trade.exit_price:.2f}")
                    self.logger.info(f"PnL:    ${trade.pnl:.2f} ({trade.pnl_percent:.2f}%)")
                    self.logger.info(f"Reason: {trade.exit_reason}")
                    self.logger.info(f"{'='*60}\n")
    
    def run_once(self):
        """Run one iteration of the trading loop"""
        try:
            # Update market data
            self.update_data()
            
            # Check trading conditions
            conditions = self.check_trading_conditions()
            
            if not conditions['mt5_connected']:
                self.logger.error("MT5 not connected!")
                return
            
            if not conditions['data_loaded']:
                self.logger.warning("Market data not loaded")
                return
            
            if not conditions['sufficient_data']:
                self.logger.warning("Insufficient historical data")
                return
            
            # Update existing positions
            self.update_positions()
            
            # Check for new signals if we can trade
            if conditions['can_trade']:
                # Generate signal
                signal = self.signal_generator.generate_signal(self.data_1h, self.data_daily)
                
                if signal:
                    self.process_signal(signal)
            else:
                reason = conditions.get('trade_check_reason', 'Unknown')
                self.logger.debug(f"Cannot trade: {reason}")
            
            # Log current status
            account = self.mt5.get_account_info()
            stats = self.risk_manager.get_statistics()
            
            self.logger.info(f"\n{'='*60}")
            self.logger.info("STATUS UPDATE")
            self.logger.info(f"{'='*60}")
            self.logger.info(f"Account Balance:  ${account.get('balance', 0):,.2f}")
            self.logger.info(f"Account Equity:   ${account.get('equity', 0):,.2f}")
            self.logger.info(f"Open Positions:   {len(self.mt5_positions if self.live_mode else self.risk_manager.positions)}")
            self.logger.info(f"Total Trades:     {stats['total_trades']}")
            self.logger.info(f"Win Rate:         {stats['win_rate']*100:.1f}%")
            self.logger.info(f"Profit Factor:    {stats['profit_factor']:.2f}")
            self.logger.info(f"{'='*60}\n")
            
        except Exception as e:
            self.logger.error(f"Error in trading loop: {e}", exc_info=True)
    
    def run(self, update_interval: int = 3600):
        """
        Run the trading bot continuously
        
        Args:
            update_interval: Seconds between updates (default 3600 = 1 hour)
        """
        self.is_running = True
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info("MT5 TRADING BOT STARTED")
        self.logger.info(f"Mode: {'LIVE TRADING' if self.live_mode else 'PAPER TRADING'}")
        self.logger.info(f"Update Interval: {update_interval}s")
        self.logger.info(f"{'='*60}\n")
        
        try:
            while self.is_running:
                self.run_once()
                
                # Wait for next update
                self.logger.debug(f"Waiting {update_interval}s until next update...")
                time.sleep(update_interval)
                
        except KeyboardInterrupt:
            self.logger.info("\nBot stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.stop()
    
    def stop(self):
        """Stop the trading bot and cleanup"""
        self.is_running = False
        
        # Close positions if requested
        if self.live_mode:
            self.logger.warning("Bot stopping - positions remain open in MT5")
            self.logger.warning("Close positions manually if desired")
        
        # Print final statistics
        account = self.mt5.get_account_info()
        stats = self.risk_manager.get_statistics()
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info("MT5 TRADING BOT STOPPED")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Final Balance:   ${account.get('balance', 0):,.2f}")
        self.logger.info(f"Final Equity:    ${account.get('equity', 0):,.2f}")
        self.logger.info(f"Total Trades:    {stats['total_trades']}")
        self.logger.info(f"Win Rate:        {stats['win_rate']*100:.1f}%")
        self.logger.info(f"Profit Factor:   {stats['profit_factor']:.2f}")
        self.logger.info(f"Max Drawdown:    {stats['max_drawdown']*100:.2f}%")
        self.logger.info(f"{'='*60}\n")
        
        # Disconnect MT5
        self.mt5.disconnect()


if __name__ == "__main__":
    from mt5_connector import quick_connect
    
    # Quick connection to MT5
    mt5 = quick_connect(symbol="XAUUSD")
    
    if mt5:
        print("MT5 connected successfully!")
        print("\nTo run the bot:")
        print("  config = TradingConfig()")
        print("  bot = XAUUSDTradingBotMT5(config, mt5, live_mode=False)")
        print("  bot.run()")
    else:
        print("Failed to connect to MT5")
        print("Make sure MT5 is running and you're logged in")
