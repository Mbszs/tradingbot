"""
MT5 Backtest Example
Demonstrates backtesting with real MT5 historical data
"""

import pandas as pd
from datetime import datetime
from config import TradingConfig
from backtester import Backtester
from mt5_connector import MT5Connector


def backtest_with_mt5_data():
    """
    Run backtest using data from MT5
    """
    print("="*70)
    print("XAU/USD Trading Bot - MT5 Backtest")
    print("="*70)
    print()
    
    # Connect to MT5
    print("Connecting to MT5...")
    mt5 = MT5Connector(symbol="XAUUSD")
    
    if not mt5.connect():
        print("ERROR: Failed to connect to MT5")
        print("Make sure:")
        print("  1. MT5 terminal is running")
        print("  2. You are logged into your account")
        print("  3. XAUUSD is in Market Watch")
        return
    
    print("MT5 connected successfully!\n")
    
    # Get historical data
    print("Downloading historical data from MT5...")
    print("This may take a moment...\n")
    
    try:
        # Get data for backtesting
        # For a thorough backtest, get 2+ years of data
        df_1h = mt5.get_historical_data('1h', bars=10000)  # ~1 year of 1H data
        df_4h = mt5.get_historical_data('4h', bars=4000)   # ~2 years of 4H data
        
        if df_1h.empty or df_4h.empty:
            print("ERROR: Failed to download data from MT5")
            mt5.disconnect()
            return
        
        print(f"✓ Downloaded 1H data: {len(df_1h)} bars")
        print(f"  Date range: {df_1h.index[0]} to {df_1h.index[-1]}")
        print(f"✓ Downloaded 4H data: {len(df_4h)} bars")
        print(f"  Date range: {df_4h.index[0]} to {df_4h.index[-1]}")
        print()
        
        # Show sample data
        print("Sample 1H data:")
        print(df_1h.tail())
        print()
        
        # Initialize configuration
        config = TradingConfig()
        
        print("Configuration:")
        print(f"  Risk per trade: {config.RISK_PER_TRADE*100}%")
        print(f"  Stop loss: {config.STOP_LOSS_ATR} ATR")
        print(f"  Take profit 1: {config.TAKE_PROFIT_1}R")
        print(f"  Take profit 2: {config.TAKE_PROFIT_2}R")
        print()
        
        # Ask for initial capital
        capital_input = input("Enter initial capital (default 10000): ").strip()
        initial_capital = float(capital_input) if capital_input else 10000.0
        
        # Run backtest
        print("\n" + "="*70)
        print("STARTING BACKTEST")
        print("="*70)
        print()
        
        backtester = Backtester(config)
        results = backtester.run_backtest(
            df_entry=df_1h,
            df_htf=df_4h,
            initial_capital=initial_capital
        )
        
        # Print results
        print("\n" + "="*70)
        backtester.print_results(results)
        
        # Save results
        print("\nSaving results...")
        import os
        os.makedirs('results', exist_ok=True)
        
        backtester.save_results(results, 'results/mt5_backtest_results.json')
        
        # Plot results
        try:
            backtester.plot_results(results, save_path='results/mt5_backtest_chart.png')
            print("✓ Chart saved to: results/mt5_backtest_chart.png")
        except Exception as e:
            print(f"Could not generate chart: {e}")
        
        # Show trade summary
        if results['trades']:
            print("\n" + "="*70)
            print("RECENT TRADES (Last 5)")
            print("="*70)
            
            for i, trade in enumerate(results['trades'][-5:]):
                pnl_symbol = "✓" if trade.pnl > 0 else "✗"
                print(f"\n{pnl_symbol} Trade {len(results['trades']) - 4 + i}:")
                print(f"  Type:    {trade.position_type.upper()}")
                print(f"  Entry:   ${trade.entry_price:.2f} @ {trade.entry_time}")
                print(f"  Exit:    ${trade.exit_price:.2f} @ {trade.exit_time}")
                print(f"  PnL:     ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)")
                print(f"  R:R:     {trade.risk_reward:.2f}")
                print(f"  Reason:  {trade.exit_reason}")
        
        # Ask to optimize parameters
        print("\n" + "="*70)
        optimize = input("\nRun parameter optimization? (y/n): ").strip().lower()
        
        if optimize == 'y':
            run_optimization(df_1h, df_4h, initial_capital)
        
    except Exception as e:
        print(f"\nERROR during backtest: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Disconnect MT5
        mt5.disconnect()
        print("\n" + "="*70)
        print("Backtest complete!")
        print("="*70)


def run_optimization(df_1h, df_4h, initial_capital):
    """Run parameter optimization"""
    print("\n" + "="*70)
    print("PARAMETER OPTIMIZATION")
    print("="*70)
    print("\nTesting different parameter combinations...")
    print("This may take several minutes...\n")
    
    # Parameters to test
    risk_levels = [0.005, 0.01, 0.015, 0.02]
    stop_loss_multipliers = [1.0, 1.5, 2.0]
    fvg_sizes = [0.2, 0.3, 0.4, 0.5]
    
    results_list = []
    
    total_tests = len(risk_levels) * len(stop_loss_multipliers) * len(fvg_sizes)
    current_test = 0
    
    print(f"Total combinations to test: {total_tests}\n")
    
    for risk in risk_levels:
        for sl_mult in stop_loss_multipliers:
            for fvg_size in fvg_sizes:
                current_test += 1
                
                # Create config
                config = TradingConfig()
                config.RISK_PER_TRADE = risk
                config.STOP_LOSS_ATR = sl_mult
                config.FVG_MIN_SIZE = fvg_size
                
                # Run backtest
                backtester = Backtester(config)
                
                try:
                    results = backtester.run_backtest(df_1h, df_4h, initial_capital)
                    stats = results['statistics']
                    
                    # Store results
                    result_entry = {
                        'risk': risk,
                        'sl_mult': sl_mult,
                        'fvg_size': fvg_size,
                        'return': stats['total_return'],
                        'win_rate': stats['win_rate'],
                        'profit_factor': stats['profit_factor'],
                        'max_dd': stats['max_drawdown'],
                        'total_trades': stats['total_trades']
                    }
                    results_list.append(result_entry)
                    
                    print(f"[{current_test}/{total_tests}] "
                          f"Risk:{risk*100:.1f}% SL:{sl_mult:.1f}x FVG:{fvg_size:.1f} | "
                          f"Return:{stats['total_return']*100:+.1f}% "
                          f"WR:{stats['win_rate']*100:.0f}% "
                          f"PF:{stats['profit_factor']:.2f} "
                          f"DD:{stats['max_drawdown']*100:.1f}%")
                    
                except Exception as e:
                    print(f"[{current_test}/{total_tests}] ERROR: {e}")
    
    # Find best parameters
    print("\n" + "="*70)
    print("OPTIMIZATION RESULTS")
    print("="*70)
    
    # Sort by return
    results_list.sort(key=lambda x: x['return'], reverse=True)
    
    print("\nTop 5 by Return:")
    for i, result in enumerate(results_list[:5], 1):
        print(f"\n{i}. Risk:{result['risk']*100:.1f}% SL:{result['sl_mult']:.1f}x FVG:{result['fvg_size']:.1f}")
        print(f"   Return: {result['return']*100:+.2f}%")
        print(f"   Win Rate: {result['win_rate']*100:.1f}%")
        print(f"   Profit Factor: {result['profit_factor']:.2f}")
        print(f"   Max DD: {result['max_dd']*100:.1f}%")
        print(f"   Trades: {result['total_trades']}")
    
    # Sort by Sharpe equivalent (return / max_dd)
    results_list.sort(key=lambda x: x['return']/max(x['max_dd'], 0.01), reverse=True)
    
    print("\nTop 5 by Risk-Adjusted Return:")
    for i, result in enumerate(results_list[:5], 1):
        ratio = result['return']/max(result['max_dd'], 0.01)
        print(f"\n{i}. Risk:{result['risk']*100:.1f}% SL:{result['sl_mult']:.1f}x FVG:{result['fvg_size']:.1f}")
        print(f"   Return/DD Ratio: {ratio:.2f}")
        print(f"   Return: {result['return']*100:+.2f}%")
        print(f"   Max DD: {result['max_dd']*100:.1f}%")
        print(f"   Win Rate: {result['win_rate']*100:.1f}%")


def quick_backtest():
    """Quick backtest with recent data"""
    print("="*70)
    print("Quick Backtest - Last 3 Months")
    print("="*70)
    print()
    
    # Connect to MT5
    mt5 = MT5Connector(symbol="XAUUSD")
    
    if not mt5.connect():
        print("Failed to connect to MT5")
        return
    
    # Get recent data
    df_1h = mt5.get_historical_data('1h', bars=2160)  # ~3 months
    df_4h = mt5.get_historical_data('4h', bars=540)   # ~3 months
    
    if df_1h.empty or df_4h.empty:
        print("Failed to get data")
        mt5.disconnect()
        return
    
    print(f"Data: {df_1h.index[0]} to {df_1h.index[-1]}\n")
    
    # Run backtest
    config = TradingConfig()
    backtester = Backtester(config)
    results = backtester.run_backtest(df_1h, df_4h, initial_capital=10000)
    
    # Print summary
    stats = results['statistics']
    print(f"\nQuick Results:")
    print(f"  Total Return:   {stats['total_return']*100:+.2f}%")
    print(f"  Win Rate:       {stats['win_rate']*100:.1f}%")
    print(f"  Total Trades:   {stats['total_trades']}")
    print(f"  Profit Factor:  {stats['profit_factor']:.2f}")
    print(f"  Max Drawdown:   {stats['max_drawdown']*100:.1f}%")
    
    mt5.disconnect()


if __name__ == "__main__":
    import os
    os.makedirs('results', exist_ok=True)
    
    print("\nMT5 Backtest Options:")
    print("1. Full backtest with all data")
    print("2. Quick backtest (last 3 months)")
    print()
    
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == '2':
        quick_backtest()
    else:
        backtest_with_mt5_data()
