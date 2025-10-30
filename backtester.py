"""
Backtesting Framework
Comprehensive backtesting engine with performance metrics and visualization
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple
from datetime import datetime
import json
import os

from config import TradingConfig
from signal_generator import SignalGenerator
from risk_manager import RiskManager, Trade
from indicators import TechnicalIndicators


class Backtester:
    """Backtesting engine for the trading strategy"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.signal_generator = SignalGenerator(config)
        self.risk_manager = None  # Initialize per backtest
        self.indicators = TechnicalIndicators()
    
    def load_data(self, symbol: str, timeframe: str, 
                  start_date: str, end_date: str) -> pd.DataFrame:
        """
        Load historical data for backtesting
        In production, this would fetch from data provider (e.g., MT5, CCXT, etc.)
        """
        # Placeholder for data loading
        # In real implementation, load from CSV, database, or API
        
        print(f"Loading {symbol} data for {timeframe} from {start_date} to {end_date}")
        print("NOTE: Implement data loading from your data source")
        print("Expected columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']")
        
        # For now, return empty DataFrame with expected structure
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare and clean data for backtesting"""
        # Ensure timestamp is datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        
        # Remove any NaN values
        df = df.dropna()
        
        # Sort by timestamp
        df = df.sort_index()
        
        return df
    
    def resample_data(self, df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """Resample data to different timeframe"""
        # Map timeframe strings to pandas resample rules
        timeframe_map = {
            '1h': '1H',
            '4h': '4H',
            '1d': '1D',
            '1D': '1D'
        }
        
        rule = timeframe_map.get(target_timeframe, '1H')
        
        resampled = pd.DataFrame()
        resampled['open'] = df['open'].resample(rule).first()
        resampled['high'] = df['high'].resample(rule).max()
        resampled['low'] = df['low'].resample(rule).min()
        resampled['close'] = df['close'].resample(rule).last()
        resampled['volume'] = df['volume'].resample(rule).sum()
        
        return resampled.dropna()
    
    def run_backtest(self, df_entry: pd.DataFrame, df_htf: pd.DataFrame,
                     initial_capital: float = 10000) -> Dict:
        """
        Run backtest on historical data
        
        Args:
            df_entry: Entry timeframe data (e.g., 1H)
            df_htf: Higher timeframe data (e.g., 4H or Daily)
            initial_capital: Starting capital
            
        Returns:
            Dictionary with backtest results
        """
        print(f"\n{'='*60}")
        print(f"Starting Backtest")
        print(f"Initial Capital: ${initial_capital:,.2f}")
        print(f"Entry TF: {len(df_entry)} candles")
        print(f"HTF: {len(df_htf)} candles")
        print(f"{'='*60}\n")
        
        # Initialize risk manager
        self.risk_manager = RiskManager(self.config, initial_capital)
        
        # Track equity curve
        equity_curve = []
        signals_generated = []
        
        # Minimum data points needed for indicators
        min_lookback = max(self.config.EMA_SLOW, self.config.OB_LOOKBACK) + 50
        
        # Iterate through data
        for i in range(min_lookback, len(df_entry)):
            current_time = df_entry.index[i]
            current_price = df_entry.iloc[i]['close']
            
            # Get historical data up to current point
            hist_entry = df_entry.iloc[:i+1]
            
            # Get corresponding HTF data
            hist_htf = df_htf[df_htf.index <= current_time]
            
            if len(hist_htf) < self.config.EMA_SLOW:
                continue
            
            # Calculate current ATR
            atr_series = self.indicators.calculate_atr(
                hist_entry['high'], hist_entry['low'], hist_entry['close'], 
                self.config.ATR_PERIOD
            )
            current_atr = atr_series.iloc[-1] if len(atr_series) > 0 else 1.0
            
            # Update existing positions
            closed_trades = []
            for position in self.risk_manager.positions[:]:  # Copy list to allow removal
                trades = self.risk_manager.update_position(
                    position, current_price, current_time, current_atr
                )
                closed_trades.extend(trades)
            
            # Check for new signals if we have capacity
            if len(self.risk_manager.positions) < self.config.MAX_OPEN_TRADES:
                try:
                    signal = self.signal_generator.generate_signal(hist_entry, hist_htf)
                    
                    if signal:
                        # Try to open position
                        position = self.risk_manager.open_position(signal, current_time, current_atr)
                        
                        if position:
                            signals_generated.append({
                                'timestamp': current_time,
                                'type': signal.signal_type,
                                'price': signal.entry_price,
                                'confidence': signal.confidence,
                                'reason': signal.reason
                            })
                            
                            print(f"\n[{current_time}] {signal.signal_type.upper()} Signal Generated")
                            print(f"  Entry: ${signal.entry_price:.2f}")
                            print(f"  Stop Loss: ${signal.stop_loss:.2f}")
                            print(f"  TP1: ${signal.take_profit_1:.2f} | TP2: ${signal.take_profit_2:.2f}")
                            print(f"  Confidence: {signal.confidence:.2%}")
                            print(f"  Reason: {signal.reason}")
                            print(f"  Position Size: {position.size:.2f}")
                
                except Exception as e:
                    # Continue on error (e.g., insufficient data)
                    pass
            
            # Log closed trades
            for trade in closed_trades:
                pnl_color = '\033[92m' if trade.pnl > 0 else '\033[91m'
                reset_color = '\033[0m'
                print(f"\n[{trade.exit_time}] Trade Closed: {trade.position_type.upper()}")
                print(f"  Entry: ${trade.entry_price:.2f} → Exit: ${trade.exit_price:.2f}")
                print(f"  {pnl_color}PnL: ${trade.pnl:.2f} ({trade.pnl_percent:.2f}%){reset_color}")
                print(f"  Reason: {trade.exit_reason} | R:R: {trade.risk_reward:.2f}")
                print(f"  Capital: ${self.risk_manager.current_capital:.2f}")
            
            # Record equity
            equity_curve.append({
                'timestamp': current_time,
                'equity': self.risk_manager.current_capital,
                'open_positions': len(self.risk_manager.positions)
            })
        
        # Close any remaining positions at the end
        final_time = df_entry.index[-1]
        final_price = df_entry.iloc[-1]['close']
        
        for position in self.risk_manager.positions[:]:
            trade = self.risk_manager._close_position(position, final_price, final_time, 'end_of_backtest')
            print(f"\n[{final_time}] Position Closed at End: {trade.position_type.upper()}")
            print(f"  PnL: ${trade.pnl:.2f}")
        
        # Generate results
        stats = self.risk_manager.get_statistics()
        
        results = {
            'statistics': stats,
            'equity_curve': equity_curve,
            'trades': self.risk_manager.trade_history,
            'signals': signals_generated,
            'config': self.config
        }
        
        return results
    
    def calculate_performance_metrics(self, results: Dict) -> Dict:
        """Calculate additional performance metrics"""
        trades = results['trades']
        equity_curve = pd.DataFrame(results['equity_curve'])
        
        if len(trades) == 0:
            return {}
        
        # Equity curve metrics
        equity_curve['returns'] = equity_curve['equity'].pct_change()
        
        # Sharpe Ratio (assuming 252 trading days)
        sharpe = (equity_curve['returns'].mean() / equity_curve['returns'].std()) * np.sqrt(252) \
                 if equity_curve['returns'].std() > 0 else 0
        
        # Sortino Ratio (downside deviation)
        downside_returns = equity_curve['returns'][equity_curve['returns'] < 0]
        sortino = (equity_curve['returns'].mean() / downside_returns.std()) * np.sqrt(252) \
                  if len(downside_returns) > 0 and downside_returns.std() > 0 else 0
        
        # Calmar Ratio (return / max drawdown)
        total_return = results['statistics']['total_return']
        max_dd = results['statistics']['max_drawdown']
        calmar = total_return / max_dd if max_dd > 0 else 0
        
        # Trade duration analysis
        trade_durations = [(t.exit_time - t.entry_time).total_seconds() / 3600 
                          for t in trades]  # in hours
        
        # Win/Loss streaks
        win_streak = 0
        loss_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        for trade in trades:
            if trade.pnl > 0:
                win_streak += 1
                loss_streak = 0
                max_win_streak = max(max_win_streak, win_streak)
            else:
                loss_streak += 1
                win_streak = 0
                max_loss_streak = max(max_loss_streak, loss_streak)
        
        return {
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'avg_trade_duration_hours': np.mean(trade_durations) if trade_durations else 0,
            'max_win_streak': max_win_streak,
            'max_loss_streak': max_loss_streak,
            'expectancy': np.mean([t.pnl for t in trades]) if trades else 0
        }
    
    def print_results(self, results: Dict):
        """Print backtest results in formatted way"""
        stats = results['statistics']
        perf = self.calculate_performance_metrics(results)
        
        print(f"\n{'='*60}")
        print(f"BACKTEST RESULTS")
        print(f"{'='*60}\n")
        
        print(f"Overall Performance:")
        print(f"  Initial Capital:     ${self.config.INITIAL_CAPITAL:,.2f}")
        print(f"  Final Capital:       ${stats['final_capital']:,.2f}")
        print(f"  Total Return:        {stats['total_return']*100:.2f}%")
        print(f"  Max Drawdown:        {stats['max_drawdown']*100:.2f}%")
        
        print(f"\nTrade Statistics:")
        print(f"  Total Trades:        {stats['total_trades']}")
        print(f"  Winning Trades:      {stats['winning_trades']}")
        print(f"  Losing Trades:       {stats['losing_trades']}")
        print(f"  Win Rate:            {stats['win_rate']*100:.2f}%")
        print(f"  Profit Factor:       {stats['profit_factor']:.2f}")
        
        print(f"\nRisk Metrics:")
        print(f"  Average Win:         ${stats['avg_win']:.2f}")
        print(f"  Average Loss:        ${stats['avg_loss']:.2f}")
        print(f"  Average R:R:         {stats['avg_risk_reward']:.2f}")
        print(f"  Expectancy:          ${perf.get('expectancy', 0):.2f}")
        
        print(f"\nAdvanced Metrics:")
        print(f"  Sharpe Ratio:        {perf.get('sharpe_ratio', 0):.2f}")
        print(f"  Sortino Ratio:       {perf.get('sortino_ratio', 0):.2f}")
        print(f"  Calmar Ratio:        {perf.get('calmar_ratio', 0):.2f}")
        
        print(f"\nTrade Duration:")
        print(f"  Avg Duration:        {perf.get('avg_trade_duration_hours', 0):.1f} hours")
        
        print(f"\nStreaks:")
        print(f"  Max Win Streak:      {perf.get('max_win_streak', 0)}")
        print(f"  Max Loss Streak:     {perf.get('max_loss_streak', 0)}")
        
        print(f"\n{'='*60}\n")
    
    def plot_results(self, results: Dict, save_path: str = None):
        """Plot backtest results"""
        equity_curve = pd.DataFrame(results['equity_curve'])
        trades = results['trades']
        
        # Create figure with subplots
        fig, axes = plt.subplots(3, 2, figsize=(15, 12))
        fig.suptitle('XAU/USD Trading Bot - Backtest Results', fontsize=16, fontweight='bold')
        
        # 1. Equity Curve
        ax1 = axes[0, 0]
        ax1.plot(equity_curve['timestamp'], equity_curve['equity'], linewidth=2, color='blue')
        ax1.axhline(y=self.config.INITIAL_CAPITAL, color='gray', linestyle='--', alpha=0.5)
        ax1.set_title('Equity Curve', fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Capital ($)')
        ax1.grid(True, alpha=0.3)
        
        # 2. Drawdown
        ax2 = axes[0, 1]
        equity = equity_curve['equity'].values
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak * 100
        ax2.fill_between(range(len(drawdown)), drawdown, 0, color='red', alpha=0.3)
        ax2.set_title('Drawdown', fontweight='bold')
        ax2.set_xlabel('Trade Number')
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True, alpha=0.3)
        
        # 3. Trade PnL Distribution
        ax3 = axes[1, 0]
        pnls = [t.pnl for t in trades]
        ax3.hist(pnls, bins=30, color='blue', alpha=0.7, edgecolor='black')
        ax3.axvline(x=0, color='red', linestyle='--', linewidth=2)
        ax3.set_title('Trade PnL Distribution', fontweight='bold')
        ax3.set_xlabel('PnL ($)')
        ax3.set_ylabel('Frequency')
        ax3.grid(True, alpha=0.3)
        
        # 4. Cumulative PnL
        ax4 = axes[1, 1]
        cumulative_pnl = np.cumsum(pnls)
        ax4.plot(cumulative_pnl, linewidth=2, color='green')
        ax4.set_title('Cumulative PnL', fontweight='bold')
        ax4.set_xlabel('Trade Number')
        ax4.set_ylabel('Cumulative PnL ($)')
        ax4.grid(True, alpha=0.3)
        
        # 5. Win Rate Over Time (rolling)
        ax5 = axes[2, 0]
        window = min(20, len(trades) // 4)
        if window > 1:
            wins = [1 if t.pnl > 0 else 0 for t in trades]
            rolling_wr = pd.Series(wins).rolling(window=window).mean() * 100
            ax5.plot(rolling_wr, linewidth=2, color='purple')
            ax5.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
            ax5.set_title(f'Rolling Win Rate ({window} trades)', fontweight='bold')
            ax5.set_xlabel('Trade Number')
            ax5.set_ylabel('Win Rate (%)')
            ax5.grid(True, alpha=0.3)
        
        # 6. Trade Type Distribution
        ax6 = axes[2, 1]
        long_trades = sum(1 for t in trades if t.position_type == 'long')
        short_trades = sum(1 for t in trades if t.position_type == 'short')
        ax6.pie([long_trades, short_trades], labels=['Long', 'Short'], 
               autopct='%1.1f%%', startangle=90, colors=['green', 'red'])
        ax6.set_title('Trade Distribution', fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Results plot saved to: {save_path}")
        
        plt.show()
    
    def save_results(self, results: Dict, filepath: str):
        """Save backtest results to JSON file"""
        # Prepare data for JSON serialization
        save_data = {
            'statistics': results['statistics'],
            'performance': self.calculate_performance_metrics(results),
            'config': {
                'symbol': self.config.SYMBOL,
                'timeframe_entry': self.config.TIMEFRAME_ENTRY,
                'timeframe_htf': self.config.TIMEFRAME_HTF,
                'initial_capital': self.config.INITIAL_CAPITAL,
                'risk_per_trade': self.config.RISK_PER_TRADE
            },
            'equity_curve': [
                {
                    'timestamp': str(e['timestamp']),
                    'equity': e['equity'],
                    'open_positions': e['open_positions']
                }
                for e in results['equity_curve']
            ],
            'trades': [
                {
                    'entry_time': str(t.entry_time),
                    'exit_time': str(t.exit_time),
                    'type': t.position_type,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'pnl': t.pnl,
                    'pnl_percent': t.pnl_percent,
                    'risk_reward': t.risk_reward,
                    'exit_reason': t.exit_reason
                }
                for t in results['trades']
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"Results saved to: {filepath}")


if __name__ == "__main__":
    # Example usage
    config = TradingConfig()
    backtester = Backtester(config)
    
    print("Backtester initialized successfully!")
    print("\nTo run a backtest:")
    print("1. Load your historical data (1H and 4H/Daily timeframes)")
    print("2. Call backtester.run_backtest(df_1h, df_4h)")
    print("3. Use backtester.print_results() and backtester.plot_results()")
