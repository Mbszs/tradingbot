"""
Risk Management Module
Handles position sizing, stop loss, take profit, and trade management
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class TradeDirection(Enum):
    """Trade direction"""
    LONG = "long"
    SHORT = "short"


class TradeStatus(Enum):
    """Trade status"""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class Trade:
    """Represents a trading position"""
    trade_id: str
    symbol: str
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    partial_tp: Optional[float] = None
    
    position_size: float = 0.0  # Lot size
    risk_amount: float = 0.0    # Dollar risk
    risk_pct: float = 0.0       # Percentage risk
    
    status: TradeStatus = TradeStatus.PENDING
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    
    pnl: float = 0.0
    pnl_pct: float = 0.0
    
    breakeven_moved: bool = False
    partial_closed: bool = False
    
    metadata: Dict = field(default_factory=dict)


@dataclass
class TradeStats:
    """Trading statistics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    largest_win: float = 0.0
    largest_loss: float = 0.0


class RiskManager:
    """
    Manages all risk-related aspects of trading:
    - Position sizing
    - Stop loss and take profit calculation
    - Trade management (partial TP, breakeven)
    - Daily drawdown limits
    - Session trade limits
    """
    
    def __init__(self, config: Dict):
        self.config = config
        
        self.account_balance = config.get('account_balance', 10000)
        self.risk_per_trade_pct = config.get('risk_per_trade_pct', 1.0)
        self.max_daily_drawdown_pct = config.get('max_daily_drawdown_pct', 3.0)
        self.max_trades_per_session = config.get('max_trades_per_session', 2)
        self.max_open_positions = config.get('max_open_positions', 1)
        self.min_rr_ratio = config.get('min_rr_ratio', 2.0)
        self.partial_tp_pct = config.get('partial_tp_pct', 50)
        self.breakeven_trigger_r = config.get('breakeven_trigger_r', 1.0)
        
        # Trade tracking
        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.daily_trades: Dict[str, int] = {}  # session -> count
        self.daily_pnl: float = 0.0
        self.starting_balance: float = self.account_balance
    
    def calculate_position_size(self, entry_price: float, 
                               stop_loss: float,
                               direction: TradeDirection) -> Tuple[float, float]:
        """
        Calculate position size based on risk percentage
        
        For XAUUSD:
        - 1 standard lot = 100 oz
        - Pip value per lot = $1 per 0.1 pip
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            direction: Trade direction
            
        Returns:
            Tuple of (position_size_lots, risk_amount_dollars)
        """
        # Calculate stop loss in pips
        sl_distance = abs(entry_price - stop_loss)
        
        # Risk amount in dollars
        risk_amount = self.account_balance * (self.risk_per_trade_pct / 100)
        
        # Calculate position size
        # For XAUUSD: 1 pip = 0.01, pip value per lot = $10
        pip_value_per_lot = 10.0
        sl_in_pips = sl_distance / 0.01
        
        if sl_in_pips > 0:
            position_size = risk_amount / (sl_in_pips * pip_value_per_lot)
        else:
            position_size = 0.01  # Minimum position
        
        # Round to 2 decimal places (0.01 lot increments)
        position_size = round(position_size, 2)
        
        return position_size, risk_amount
    
    def calculate_take_profit(self, entry_price: float,
                             stop_loss: float,
                             direction: TradeDirection,
                             rr_ratio: Optional[float] = None) -> float:
        """
        Calculate take profit based on risk:reward ratio
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            direction: Trade direction
            rr_ratio: Risk:Reward ratio (uses min_rr_ratio if None)
            
        Returns:
            Take profit price
        """
        if rr_ratio is None:
            rr_ratio = self.min_rr_ratio
        
        sl_distance = abs(entry_price - stop_loss)
        tp_distance = sl_distance * rr_ratio
        
        if direction == TradeDirection.LONG:
            take_profit = entry_price + tp_distance
        else:
            take_profit = entry_price - tp_distance
        
        return take_profit
    
    def calculate_partial_tp(self, entry_price: float,
                            take_profit: float) -> float:
        """
        Calculate partial take profit level (typically at 1R)
        
        Args:
            entry_price: Entry price
            take_profit: Full take profit price
            
        Returns:
            Partial TP price
        """
        # Partial TP at midpoint by default, or at 1R
        distance = abs(take_profit - entry_price)
        partial_distance = distance / 2
        
        if entry_price < take_profit:  # Long
            return entry_price + partial_distance
        else:  # Short
            return entry_price - partial_distance
    
    def create_trade(self, symbol: str,
                    direction: TradeDirection,
                    entry_price: float,
                    stop_loss: float,
                    take_profit: Optional[float] = None,
                    metadata: Optional[Dict] = None) -> Optional[Trade]:
        """
        Create a new trade with proper risk management
        
        Args:
            symbol: Trading symbol
            direction: Trade direction
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price (calculated if None)
            metadata: Additional trade information
            
        Returns:
            Trade object if valid, None otherwise
        """
        # Check if trading is allowed
        if not self.can_open_trade():
            return None
        
        # Calculate TP if not provided
        if take_profit is None:
            take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
        
        # Validate RR ratio
        sl_distance = abs(entry_price - stop_loss)
        tp_distance = abs(take_profit - entry_price)
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        if rr_ratio < self.min_rr_ratio:
            return None  # RR ratio too low
        
        # Calculate position size
        position_size, risk_amount = self.calculate_position_size(
            entry_price, stop_loss, direction
        )
        
        # Create trade
        trade_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            partial_tp=self.calculate_partial_tp(entry_price, take_profit),
            position_size=position_size,
            risk_amount=risk_amount,
            risk_pct=self.risk_per_trade_pct,
            status=TradeStatus.PENDING,
            metadata=metadata or {}
        )
        
        return trade
    
    def open_trade(self, trade: Trade) -> bool:
        """
        Open a trade
        
        Args:
            trade: Trade object
            
        Returns:
            True if opened successfully
        """
        if not self.can_open_trade():
            return False
        
        trade.status = TradeStatus.OPEN
        trade.entry_time = datetime.now()
        self.open_trades.append(trade)
        
        return True
    
    def close_trade(self, trade: Trade, exit_price: float, 
                   reason: str = "target") -> None:
        """
        Close a trade and update statistics
        
        Args:
            trade: Trade to close
            exit_price: Exit price
            reason: Reason for closing
        """
        trade.status = TradeStatus.CLOSED
        trade.exit_time = datetime.now()
        trade.exit_price = exit_price
        trade.metadata['close_reason'] = reason
        
        # Calculate P&L
        if trade.direction == TradeDirection.LONG:
            price_diff = exit_price - trade.entry_price
        else:
            price_diff = trade.entry_price - exit_price
        
        # P&L in pips
        pnl_pips = price_diff / 0.01
        
        # P&L in dollars
        pip_value = 10.0 * trade.position_size
        trade.pnl = pnl_pips * pip_value
        trade.pnl_pct = (trade.pnl / self.account_balance) * 100
        
        # Update account
        self.account_balance += trade.pnl
        self.daily_pnl += trade.pnl
        
        # Move to closed trades
        self.open_trades.remove(trade)
        self.closed_trades.append(trade)
    
    def manage_trade(self, trade: Trade, current_price: float) -> None:
        """
        Manage open trade (partial TP, breakeven, stop loss)
        
        Args:
            trade: Open trade
            current_price: Current market price
        """
        if trade.status != TradeStatus.OPEN:
            return
        
        # Check stop loss
        if trade.direction == TradeDirection.LONG:
            if current_price <= trade.stop_loss:
                self.close_trade(trade, current_price, "stop_loss")
                return
        else:
            if current_price >= trade.stop_loss:
                self.close_trade(trade, current_price, "stop_loss")
                return
        
        # Check take profit
        if trade.direction == TradeDirection.LONG:
            if current_price >= trade.take_profit:
                self.close_trade(trade, current_price, "take_profit")
                return
        else:
            if current_price <= trade.take_profit:
                self.close_trade(trade, current_price, "take_profit")
                return
        
        # Check partial TP
        if not trade.partial_closed and trade.partial_tp:
            if trade.direction == TradeDirection.LONG:
                if current_price >= trade.partial_tp:
                    trade.partial_closed = True
                    # In real implementation, reduce position size
            else:
                if current_price <= trade.partial_tp:
                    trade.partial_closed = True
        
        # Check breakeven
        if not trade.breakeven_moved:
            sl_distance = abs(trade.entry_price - trade.stop_loss)
            r_distance = sl_distance * self.breakeven_trigger_r
            
            if trade.direction == TradeDirection.LONG:
                if current_price >= trade.entry_price + r_distance:
                    trade.stop_loss = trade.entry_price
                    trade.breakeven_moved = True
            else:
                if current_price <= trade.entry_price - r_distance:
                    trade.stop_loss = trade.entry_price
                    trade.breakeven_moved = True
    
    def can_open_trade(self) -> bool:
        """
        Check if a new trade can be opened
        
        Returns:
            True if trade can be opened
        """
        # Check max open positions
        if len(self.open_trades) >= self.max_open_positions:
            return False
        
        # Check daily drawdown
        daily_dd_pct = (self.daily_pnl / self.starting_balance) * 100
        if daily_dd_pct <= -self.max_daily_drawdown_pct:
            return False
        
        return True
    
    def can_open_session_trade(self, session: str) -> bool:
        """
        Check if a trade can be opened in the current session
        
        Args:
            session: Session name
            
        Returns:
            True if trade can be opened
        """
        session_trades = self.daily_trades.get(session, 0)
        return session_trades < self.max_trades_per_session
    
    def register_session_trade(self, session: str) -> None:
        """
        Register a trade for a session
        
        Args:
            session: Session name
        """
        if session not in self.daily_trades:
            self.daily_trades[session] = 0
        self.daily_trades[session] += 1
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics (call at start of new day)"""
        self.daily_trades = {}
        self.daily_pnl = 0.0
        self.starting_balance = self.account_balance
    
    def get_statistics(self) -> TradeStats:
        """
        Calculate trading statistics
        
        Returns:
            TradeStats object
        """
        if not self.closed_trades:
            return TradeStats()
        
        stats = TradeStats()
        stats.total_trades = len(self.closed_trades)
        
        wins = [t for t in self.closed_trades if t.pnl > 0]
        losses = [t for t in self.closed_trades if t.pnl < 0]
        breakevens = [t for t in self.closed_trades if t.pnl == 0]
        
        stats.winning_trades = len(wins)
        stats.losing_trades = len(losses)
        stats.breakeven_trades = len(breakevens)
        
        stats.total_pnl = sum(t.pnl for t in self.closed_trades)
        stats.total_pnl_pct = (stats.total_pnl / self.starting_balance) * 100
        
        if stats.total_trades > 0:
            stats.win_rate = (stats.winning_trades / stats.total_trades) * 100
        
        if wins:
            stats.avg_win = sum(t.pnl for t in wins) / len(wins)
            stats.largest_win = max(t.pnl for t in wins)
        
        if losses:
            stats.avg_loss = sum(t.pnl for t in losses) / len(losses)
            stats.largest_loss = min(t.pnl for t in losses)
        
        # Profit factor
        total_wins = sum(t.pnl for t in wins) if wins else 0
        total_losses = abs(sum(t.pnl for t in losses)) if losses else 0
        
        if total_losses > 0:
            stats.profit_factor = total_wins / total_losses
        
        return stats
