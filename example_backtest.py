"""
Example Backtesting Script
Demonstrates how to use the XAU/USD trading bot for backtesting
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import TradingConfig
from backtester import Backtester


def generate_sample_data(start_date: str, end_date: str, timeframe: str = '1h') -> pd.DataFrame:
    """
    Generate sample OHLCV data for demonstration
    
    In production, replace this with actual data loading from:
    - CSV files
    - Database
    - Broker API (MT5, CCXT, etc.)
    - Market data provider
    """
    print(f"Generating sample {timeframe} data from {start_date} to {end_date}")
    
    # Create date range
    if timeframe == '1h':
        freq = '1H'
        periods = 8760  # ~1 year of hourly data
    elif timeframe == '4h':
        freq = '4H'
        periods = 2190  # ~1 year of 4H data
    else:  # daily
        freq = '1D'
        periods = 365  # 1 year of daily data
    
    dates = pd.date_range(start=start_date, periods=periods, freq=freq)
    
    # Generate realistic-looking price data
    # Starting price for XAU/USD
    base_price = 1950.0
    
    # Generate random walk with trend
    returns = np.random.normal(0.0002, 0.008, len(dates))  # Small positive drift
    prices = base_price * np.exp(np.cumsum(returns))
    
    # Generate OHLC data
    data = []
    for i, date in enumerate(dates):
        price = prices[i]
        
        # Generate realistic high/low/open/close
        daily_range = price * np.random.uniform(0.003, 0.015)  # 0.3-1.5% daily range
        
        open_price = price + np.random.uniform(-daily_range/2, daily_range/2)
        close_price = price + np.random.uniform(-daily_range/2, daily_range/2)
        high_price = max(open_price, close_price) + np.random.uniform(0, daily_range/2)
        low_price = min(open_price, close_price) - np.random.uniform(0, daily_range/2)
        
        volume = np.random.uniform(50000, 200000)  # Random volume
        
        data.append({
            'timestamp': date,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    
    return df


def load_real_data_example():
    """
    Example of loading real data from various sources
    Uncomment and modify based on your data source
    """
    
    # Example 1: Load from CSV
    """
    df_1h = pd.read_csv('data/xauusd_1h.csv', parse_dates=['timestamp'])
    df_1h.set_index('timestamp', inplace=True)
    
    df_4h = pd.read_csv('data/xauusd_4h.csv', parse_dates=['timestamp'])
    df_4h.set_index('timestamp', inplace=True)
    
    return df_1h, df_4h
    """
    
    # Example 2: Load from MetaTrader 5
    """
    import MetaTrader5 as mt5
    
    if not mt5.initialize():
        print("MT5 initialization failed")
        return None, None
    
    # Get 1H data
    rates_1h = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 10000)
    df_1h = pd.DataFrame(rates_1h)
    df_1h['timestamp'] = pd.to_datetime(df_1h['time'], unit='s')
    df_1h.set_index('timestamp', inplace=True)
    df_1h = df_1h[['open', 'high', 'low', 'close', 'tick_volume']].rename(
        columns={'tick_volume': 'volume'}
    )
    
    # Get 4H data
    rates_4h = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H4, 0, 2500)
    df_4h = pd.DataFrame(rates_4h)
    df_4h['timestamp'] = pd.to_datetime(df_4h['time'], unit='s')
    df_4h.set_index('timestamp', inplace=True)
    df_4h = df_4h[['open', 'high', 'low', 'close', 'tick_volume']].rename(
        columns={'tick_volume': 'volume'}
    )
    
    mt5.shutdown()
    return df_1h, df_4h
    """
    
    # Example 3: Load from yfinance (free data)
    """
    import yfinance as yf
    
    # Gold futures
    ticker = yf.Ticker("GC=F")
    
    # Get 1H data (limited history)
    df_1h = ticker.history(period="60d", interval="1h")
    df_1h.index.name = 'timestamp'
    df_1h = df_1h[['Open', 'High', 'Low', 'Close', 'Volume']].rename(
        columns={'Open': 'open', 'High': 'high', 'Low': 'low', 
                'Close': 'close', 'Volume': 'volume'}
    )
    
    # Get 1D data for HTF
    df_1d = ticker.history(period="2y", interval="1d")
    df_1d.index.name = 'timestamp'
    df_1d = df_1d[['Open', 'High', 'Low', 'Close', 'Volume']].rename(
        columns={'Open': 'open', 'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume'}
    )
    
    return df_1h, df_1d
    """
    
    pass


def run_backtest_example():
    """Run a complete backtest example"""
    
    print("="*70)
    print("XAU/USD Trading Bot - Backtesting Example")
    print("="*70)
    print()
    
    # Initialize configuration
    config = TradingConfig()
    
    # Generate or load data
    print("Loading data...")
    
    # Option 1: Use sample data for demonstration
    df_1h = generate_sample_data('2023-01-01', '2024-01-01', '1h')
    df_4h = generate_sample_data('2023-01-01', '2024-01-01', '4h')
    
    # Option 2: Load real data (uncomment and implement)
    # df_1h, df_4h = load_real_data_example()
    
    print(f"1H Data: {len(df_1h)} candles")
    print(f"4H Data: {len(df_4h)} candles")
    print(f"Date Range: {df_1h.index[0]} to {df_1h.index[-1]}")
    print()
    
    # Initialize backtester
    backtester = Backtester(config)
    
    # Run backtest
    print("Running backtest...")
    results = backtester.run_backtest(
        df_entry=df_1h,
        df_htf=df_4h,
        initial_capital=config.INITIAL_CAPITAL
    )
    
    # Print results
    print("\n" + "="*70)
    backtester.print_results(results)
    
    # Calculate additional metrics
    print("Calculating advanced metrics...")
    perf = backtester.calculate_performance_metrics(results)
    
    # Save results
    print("\nSaving results...")
    backtester.save_results(results, 'results/backtest_results.json')
    
    # Plot results
    print("Generating plots...")
    try:
        backtester.plot_results(results, save_path='results/backtest_results.png')
    except Exception as e:
        print(f"Note: Could not generate plots - {e}")
        print("This is normal if running in headless environment")
    
    # Print trade summary
    if results['trades']:
        print("\n" + "="*70)
        print("TRADE SUMMARY (First 5 trades)")
        print("="*70)
        
        for i, trade in enumerate(results['trades'][:5]):
            print(f"\nTrade {i+1}:")
            print(f"  Type:       {trade.position_type.upper()}")
            print(f"  Entry:      ${trade.entry_price:.2f} @ {trade.entry_time}")
            print(f"  Exit:       ${trade.exit_price:.2f} @ {trade.exit_time}")
            print(f"  PnL:        ${trade.pnl:.2f} ({trade.pnl_percent:.2f}%)")
            print(f"  R:R:        {trade.risk_reward:.2f}")
            print(f"  Exit Reason: {trade.exit_reason}")
        
        if len(results['trades']) > 5:
            print(f"\n... and {len(results['trades']) - 5} more trades")
    
    print("\n" + "="*70)
    print("Backtest complete!")
    print("="*70)
    
    return results


def run_optimization_example():
    """
    Example of parameter optimization
    Test different parameter combinations to find optimal settings
    """
    print("\n" + "="*70)
    print("PARAMETER OPTIMIZATION EXAMPLE")
    print("="*70)
    
    # Generate data
    df_1h = generate_sample_data('2023-01-01', '2024-01-01', '1h')
    df_4h = generate_sample_data('2023-01-01', '2024-01-01', '4h')
    
    # Parameters to test
    risk_levels = [0.005, 0.01, 0.015, 0.02]
    stop_loss_multipliers = [1.0, 1.5, 2.0]
    
    best_result = None
    best_return = -float('inf')
    best_params = None
    
    print("\nTesting parameter combinations...\n")
    
    for risk in risk_levels:
        for sl_mult in stop_loss_multipliers:
            # Create config with test parameters
            config = TradingConfig()
            config.RISK_PER_TRADE = risk
            config.STOP_LOSS_ATR = sl_mult
            
            # Run backtest
            backtester = Backtester(config)
            try:
                results = backtester.run_backtest(df_1h, df_4h, initial_capital=10000)
                
                stats = results['statistics']
                total_return = stats['total_return']
                
                print(f"Risk: {risk*100:.1f}% | SL: {sl_mult:.1f}x ATR | "
                      f"Return: {total_return*100:.2f}% | "
                      f"Win Rate: {stats['win_rate']*100:.1f}% | "
                      f"DD: {stats['max_drawdown']*100:.2f}%")
                
                # Track best result (you can customize the optimization metric)
                if total_return > best_return and stats['max_drawdown'] < 0.20:  # <20% DD
                    best_return = total_return
                    best_result = results
                    best_params = {'risk': risk, 'sl_mult': sl_mult}
                    
            except Exception as e:
                print(f"Risk: {risk*100:.1f}% | SL: {sl_mult:.1f}x ATR | ERROR: {e}")
    
    if best_params:
        print("\n" + "="*70)
        print("BEST PARAMETERS FOUND:")
        print(f"  Risk per trade: {best_params['risk']*100:.1f}%")
        print(f"  Stop loss: {best_params['sl_mult']:.1f}x ATR")
        print(f"  Total return: {best_return*100:.2f}%")
        print("="*70)
    
    return best_params


if __name__ == "__main__":
    import os
    
    # Create results directory
    os.makedirs('results', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    
    print("\n" + "="*70)
    print("XAU/USD Trading Bot - Example Backtesting")
    print("="*70)
    print()
    print("Choose an option:")
    print("1. Run single backtest")
    print("2. Run parameter optimization")
    print("3. Both")
    print()
    
    choice = input("Enter choice (1/2/3) or press Enter for single backtest: ").strip()
    
    if choice == '2':
        run_optimization_example()
    elif choice == '3':
        run_backtest_example()
        run_optimization_example()
    else:  # Default to single backtest
        run_backtest_example()
    
    print("\n" + "="*70)
    print("Done! Check the 'results' folder for outputs.")
    print("="*70)
