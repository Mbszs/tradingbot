"""
Risk Management Module
Handles position sizing, risk calculations, and safety mechanisms
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Position:
    """Active trading position"""
    entry_time: datetime
    position_type: str  # 'long' or 'short'
    entry_price: float
    size: float  # Position size
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    remaining_size: float  # Size still in position
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    highest_price: float = 0.0  # For trailing stop
    lowest_price: float = 999999.0  # For trailing stop
    trailing_stop_active: bool = False
    trailing_stop_price: Optional[float] = None
    tp1_hit: bool = False
    tp2_hit: bool = False


@dataclass
class Trade:
    """Completed trade record"""
    entry_time: datetime
    exit_time: datetime
    position_type: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_percent: float
    risk_reward: float
    stop_loss: float
    exit_reason: str  # 'tp1', 'tp2', 'stop_loss', 'trailing_stop', 'manual'


class RiskManager:
    """Manage risk, position sizing, and trade execution"""
    
    def __init__(self, config, initial_capital: float):
        self.config = config
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: List[Position] = []
        self.trade_history: List[Trade] = []
        self.daily_pnl: Dict[str, float] = {}
        self.consecutive_losses = 0
        self.last_loss_time: Optional[datetime] = None
        self.in_cooldown = False
        self.cooldown_until: Optional[datetime] = None
    
    def calculate_position_size(self, entry_price: float, stop_loss: float,
                                risk_percent: float, atr: float = None) -> float:
        """
        Calculate position size based on risk percentage
        Optionally adjust based on ATR for dynamic sizing
        """
        # Base risk amount
        risk_amount = self.current_capital * risk_percent
        
        # Calculate risk per unit
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit == 0:
            return 0.0
        
        # Base position size
        position_size = risk_amount / risk_per_unit
        
        # Dynamic sizing based on ATR (if enabled and ATR provided)
        if self.config.DYNAMIC_SIZING and atr is not None:
            # Reduce size in high volatility, increase in low volatility
            # Normalize ATR (assume typical ATR is around entry_price * 0.01)
            typical_atr = entry_price * 0.01
            volatility_adjustment = typical_atr / atr if atr > 0 else 1.0
            
            # Apply adjustment (cap between 0.5x and 1.5x)
            volatility_adjustment = np.clip(volatility_adjustment, 0.5, 1.5)
            position_size *= volatility_adjustment
        
        # Cap position size
        max_size = self.config.MAX_POSITION_SIZE
        position_size = min(position_size, max_size)
        
        # Ensure minimum size
        position_size = max(position_size, self.config.BASE_POSITION_SIZE)
        
        return round(position_size, 2)
    
    def can_open_position(self, timestamp: datetime) -> Dict[str, any]:
        """
        Check if we can open a new position based on risk rules
        Returns dict with 'can_trade' bool and 'reason' string
        """
        # Check maximum open positions
        if len(self.positions) >= self.config.MAX_OPEN_TRADES:
            return {'can_trade': False, 'reason': 'Max open trades reached'}
        
        # Check cooldown period
        if self.in_cooldown and self.cooldown_until:
            if timestamp < self.cooldown_until:
                return {'can_trade': False, 'reason': f'In cooldown until {self.cooldown_until}'}
            else:
                # Cooldown expired
                self.in_cooldown = False
                self.cooldown_until = None
                self.consecutive_losses = 0
        
        # Check consecutive losses
        if self.consecutive_losses >= self.config.MAX_CONSECUTIVE_LOSSES:
            if not self.in_cooldown:
                # Enter cooldown
                self.in_cooldown = True
                self.cooldown_until = timestamp + timedelta(hours=self.config.COOLDOWN_PERIOD)
                return {'can_trade': False, 
                       'reason': f'Max consecutive losses reached. Cooldown until {self.cooldown_until}'}
        
        # Check daily loss limit
        date_key = timestamp.strftime('%Y-%m-%d')
        daily_loss = self.daily_pnl.get(date_key, 0.0)
        
        if daily_loss < 0:
            daily_loss_percent = abs(daily_loss) / self.current_capital
            if daily_loss_percent >= self.config.MAX_DAILY_LOSS:
                return {'can_trade': False, 
                       'reason': f'Daily loss limit reached: {daily_loss_percent*100:.2f}%'}
        
        return {'can_trade': True, 'reason': 'All checks passed'}
    
    def open_position(self, signal, timestamp: datetime, atr: float) -> Optional[Position]:
        """Open a new position based on signal"""
        # Check if we can trade
        can_trade = self.can_open_position(timestamp)
        if not can_trade['can_trade']:
            return None
        
        # Calculate position size
        risk_percent = min(self.config.RISK_PER_TRADE, self.config.MAX_RISK_PER_TRADE)
        
        # Reduce risk if confidence is low
        if signal.confidence < 0.7:
            risk_percent *= 0.7
        
        position_size = self.calculate_position_size(
            signal.entry_price, signal.stop_loss, risk_percent, atr
        )
        
        if position_size == 0:
            return None
        
        # Create position
        position = Position(
            entry_time=timestamp,
            position_type=signal.signal_type,
            entry_price=signal.entry_price,
            size=position_size,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            remaining_size=position_size,
            highest_price=signal.entry_price if signal.signal_type == 'long' else 0,
            lowest_price=signal.entry_price if signal.signal_type == 'short' else 999999
        )
        
        self.positions.append(position)
        return position
    
    def update_position(self, position: Position, current_price: float, 
                       current_time: datetime, atr: float) -> List[Trade]:
        """
        Update position with current price
        Handle partial profits, trailing stops, stop loss
        Returns list of closed trades (if any)
        """
        closed_trades = []
        
        # Update unrealized PnL
        if position.position_type == 'long':
            position.unrealized_pnl = (current_price - position.entry_price) * position.remaining_size
            position.highest_price = max(position.highest_price, current_price)
        else:  # short
            position.unrealized_pnl = (position.entry_price - current_price) * position.remaining_size
            position.lowest_price = min(position.lowest_price, current_price)
        
        # Check stop loss
        if position.position_type == 'long' and current_price <= position.stop_loss:
            trade = self._close_position(position, current_price, current_time, 'stop_loss')
            closed_trades.append(trade)
            return closed_trades
        elif position.position_type == 'short' and current_price >= position.stop_loss:
            trade = self._close_position(position, current_price, current_time, 'stop_loss')
            closed_trades.append(trade)
            return closed_trades
        
        # Check take profit 1
        if not position.tp1_hit:
            if position.position_type == 'long' and current_price >= position.take_profit_1:
                trade = self._partial_close(position, current_price, current_time, 
                                           self.config.TAKE_PROFIT_1_SIZE, 'tp1')
                closed_trades.append(trade)
                position.tp1_hit = True
                
            elif position.position_type == 'short' and current_price <= position.take_profit_1:
                trade = self._partial_close(position, current_price, current_time,
                                           self.config.TAKE_PROFIT_1_SIZE, 'tp1')
                closed_trades.append(trade)
                position.tp1_hit = True
        
        # Check take profit 2
        if not position.tp2_hit and position.tp1_hit:
            if position.position_type == 'long' and current_price >= position.take_profit_2:
                trade = self._partial_close(position, current_price, current_time,
                                           self.config.TAKE_PROFIT_2_SIZE, 'tp2')
                closed_trades.append(trade)
                position.tp2_hit = True
                
            elif position.position_type == 'short' and current_price <= position.take_profit_2:
                trade = self._partial_close(position, current_price, current_time,
                                           self.config.TAKE_PROFIT_2_SIZE, 'tp2')
                closed_trades.append(trade)
                position.tp2_hit = True
        
        # Activate trailing stop at specified R multiple
        if not position.trailing_stop_active:
            risk = abs(position.entry_price - position.stop_loss)
            
            if position.position_type == 'long':
                profit = current_price - position.entry_price
                r_multiple = profit / risk if risk > 0 else 0
                
                if r_multiple >= self.config.TRAILING_STOP_ACTIVATION:
                    position.trailing_stop_active = True
                    position.trailing_stop_price = current_price - (atr * self.config.TRAILING_STOP_ATR)
            
            else:  # short
                profit = position.entry_price - current_price
                r_multiple = profit / risk if risk > 0 else 0
                
                if r_multiple >= self.config.TRAILING_STOP_ACTIVATION:
                    position.trailing_stop_active = True
                    position.trailing_stop_price = current_price + (atr * self.config.TRAILING_STOP_ATR)
        
        # Update trailing stop
        if position.trailing_stop_active:
            if position.position_type == 'long':
                new_trailing = current_price - (atr * self.config.TRAILING_STOP_ATR)
                position.trailing_stop_price = max(position.trailing_stop_price, new_trailing)
                
                # Check if trailing stop hit
                if current_price <= position.trailing_stop_price:
                    trade = self._close_position(position, current_price, current_time, 'trailing_stop')
                    closed_trades.append(trade)
                    return closed_trades
            
            else:  # short
                new_trailing = current_price + (atr * self.config.TRAILING_STOP_ATR)
                position.trailing_stop_price = min(position.trailing_stop_price, new_trailing)
                
                # Check if trailing stop hit
                if current_price >= position.trailing_stop_price:
                    trade = self._close_position(position, current_price, current_time, 'trailing_stop')
                    closed_trades.append(trade)
                    return closed_trades
        
        return closed_trades
    
    def _partial_close(self, position: Position, exit_price: float, 
                      exit_time: datetime, close_percent: float, reason: str) -> Trade:
        """Partially close a position"""
        close_size = position.remaining_size * close_percent
        
        # Calculate PnL for closed portion
        if position.position_type == 'long':
            pnl = (exit_price - position.entry_price) * close_size
        else:
            pnl = (position.entry_price - exit_price) * close_size
        
        # Apply commission and slippage
        commission = close_size * exit_price * self.config.COMMISSION
        slippage_cost = close_size * (self.config.SLIPPAGE * 0.0001)  # Convert pips to price
        pnl -= (commission + slippage_cost)
        
        position.realized_pnl += pnl
        position.remaining_size -= close_size
        
        # Update capital
        self.current_capital += pnl
        
        # Update daily PnL
        date_key = exit_time.strftime('%Y-%m-%d')
        self.daily_pnl[date_key] = self.daily_pnl.get(date_key, 0.0) + pnl
        
        # Calculate metrics
        risk = abs(position.entry_price - position.stop_loss)
        pnl_percent = (pnl / (position.entry_price * close_size)) * 100
        risk_reward = abs(exit_price - position.entry_price) / risk if risk > 0 else 0
        
        # Create trade record
        trade = Trade(
            entry_time=position.entry_time,
            exit_time=exit_time,
            position_type=position.position_type,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size=close_size,
            pnl=pnl,
            pnl_percent=pnl_percent,
            risk_reward=risk_reward,
            stop_loss=position.stop_loss,
            exit_reason=reason
        )
        
        # Update consecutive losses
        if pnl > 0:
            self.consecutive_losses = 0
        
        return trade
    
    def _close_position(self, position: Position, exit_price: float,
                       exit_time: datetime, reason: str) -> Trade:
        """Fully close a position"""
        # Calculate PnL for remaining position
        if position.position_type == 'long':
            pnl = (exit_price - position.entry_price) * position.remaining_size
        else:
            pnl = (position.entry_price - exit_price) * position.remaining_size
        
        # Apply commission and slippage
        commission = position.remaining_size * exit_price * self.config.COMMISSION
        slippage_cost = position.remaining_size * (self.config.SLIPPAGE * 0.0001)
        pnl -= (commission + slippage_cost)
        
        # Add any previously realized PnL
        total_pnl = pnl + position.realized_pnl
        
        # Update capital
        self.current_capital += pnl
        
        # Update daily PnL
        date_key = exit_time.strftime('%Y-%m-%d')
        self.daily_pnl[date_key] = self.daily_pnl.get(date_key, 0.0) + pnl
        
        # Calculate metrics
        risk = abs(position.entry_price - position.stop_loss)
        pnl_percent = (total_pnl / (position.entry_price * position.size)) * 100
        risk_reward = abs(exit_price - position.entry_price) / risk if risk > 0 else 0
        
        # Create trade record
        trade = Trade(
            entry_time=position.entry_time,
            exit_time=exit_time,
            position_type=position.position_type,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size=position.size,
            pnl=total_pnl,
            pnl_percent=pnl_percent,
            risk_reward=risk_reward,
            stop_loss=position.stop_loss,
            exit_reason=reason
        )
        
        self.trade_history.append(trade)
        
        # Update consecutive losses
        if total_pnl < 0:
            self.consecutive_losses += 1
            self.last_loss_time = exit_time
        else:
            self.consecutive_losses = 0
        
        # Remove position
        self.positions.remove(position)
        
        return trade
    
    def get_statistics(self) -> Dict:
        """Calculate trading statistics"""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'max_drawdown': 0,
                'total_return': 0
            }
        
        wins = [t for t in self.trade_history if t.pnl > 0]
        losses = [t for t in self.trade_history if t.pnl < 0]
        
        total_trades = len(self.trade_history)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        avg_win = np.mean([t.pnl for t in wins]) if wins else 0
        avg_loss = np.mean([t.pnl for t in losses]) if losses else 0
        
        # Calculate max drawdown
        equity_curve = [self.initial_capital]
        for trade in self.trade_history:
            equity_curve.append(equity_curve[-1] + trade.pnl)
        
        peak = equity_curve[0]
        max_dd = 0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)
        
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_dd,
            'total_return': total_return,
            'final_capital': self.current_capital,
            'avg_risk_reward': np.mean([t.risk_reward for t in self.trade_history])
        }
