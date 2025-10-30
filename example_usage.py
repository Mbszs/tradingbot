"""
Example Usage Script for ICT XAUUSD Trading Bot

This script demonstrates how to use the trading bot with sample data.
In production, replace the sample data with real-time data from your broker.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from trading_bot import ICTTradingBot
from config import SYMBOL


def generate_sample_data(symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
    """
    Generate sample OHLC data for testing
    
    In production, replace this with real data fetching from:
    - MetaTrader 5: mt5.copy_rates_from_pos()
    - Oanda: oanda.get_candles()
    - Interactive Brokers: ib.reqHistoricalData()
    - Yahoo Finance: yf.download()
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe string
        bars: Number of bars to generate
        
    Returns:
        DataFrame with OHLC data
    """
    print(f"Generating sample {timeframe} data ({bars} bars)...")
    
    # Generate timestamps based on timeframe
    timeframe_minutes = {
        '1D': 1440,
        '4H': 240,
        '1H': 60,
        '15m': 15,
        '5m': 5,
        '1m': 1
    }
    
    minutes = timeframe_minutes.get(timeframe, 60)
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=bars * minutes)
    
    timestamps = pd.date_range(start=start_time, end=end_time, freq=f'{minutes}T')[:bars]
    
    # Generate realistic price data (random walk with trend)
    base_price = 2000  # XAUUSD around 2000
    price_changes = np.random.randn(bars) * 0.5 + 0.01  # Small upward trend
    prices = base_price + np.cumsum(price_changes)
    
    # Generate OHLC
    data = []
    for i, ts in enumerate(timestamps):
        open_price = prices[i]
        close_price = prices[i] + np.random.randn() * 0.2
        high_price = max(open_price, close_price) + abs(np.random.randn() * 0.1)
        low_price = min(open_price, close_price) - abs(np.random.randn() * 0.1)
        volume = np.random.randint(100, 1000)
        
        data.append({
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data, index=timestamps)
    return df


def fetch_mt5_data(symbol: str, timeframe, bars: int) -> pd.DataFrame:
    """
    Fetch real data from MetaTrader 5
    
    IMPORTANT: Uncomment and use this in production!
    
    Args:
        symbol: Trading symbol (e.g., 'XAUUSD')
        timeframe: MT5 timeframe constant (e.g., mt5.TIMEFRAME_H1)
        bars: Number of bars to fetch
        
    Returns:
        DataFrame with OHLC data
    """
    # Uncomment when using MetaTrader 5:
    """
    import MetaTrader5 as mt5
    
    if not mt5.initialize():
        print("MetaTrader 5 initialization failed")
        return None
    
    # Fetch data
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    
    if rates is None or len(rates) == 0:
        print(f"Failed to fetch data for {symbol}")
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    
    # Rename columns to match expected format
    df.rename(columns={
        'tick_volume': 'volume'
    }, inplace=True)
    
    return df[['open', 'high', 'low', 'close', 'volume']]
    """
    pass


def run_bot_with_sample_data():
    """
    Run the trading bot with sample data
    
    This is for demonstration purposes only.
    In production, use real data from your broker.
    """
    print("=" * 80)
    print("ICT XAUUSD Trading Bot - Example Usage")
    print("=" * 80)
    print()
    print("⚠️  WARNING: This is using SAMPLE DATA for demonstration.")
    print("    In production, replace with real broker data!")
    print()
    
    # Initialize the bot
    bot = ICTTradingBot()
    
    # Generate sample multi-timeframe data
    print("Preparing multi-timeframe data...")
    data = {
        'daily': generate_sample_data(SYMBOL, '1D', 100),
        '4h': generate_sample_data(SYMBOL, '4H', 200),
        '1h': generate_sample_data(SYMBOL, '1H', 500),
        '15m': generate_sample_data(SYMBOL, '15m', 1000),
        '5m': generate_sample_data(SYMBOL, '5m', 2000)
    }
    
    print("\nData Summary:")
    for tf, df in data.items():
        print(f"  {tf:6s}: {len(df)} bars | Latest: {df.iloc[-1]['close']:.2f}")
    
    print("\n" + "=" * 80)
    
    # Run the strategy
    bot.run_strategy(data)
    
    print("\n" + "=" * 80)
    print("Strategy execution complete!")
    print("=" * 80)


def run_bot_with_mt5_data():
    """
    Run the trading bot with live MetaTrader 5 data
    
    Uncomment and configure when ready for live/demo trading.
    """
    print("=" * 80)
    print("ICT XAUUSD Trading Bot - Live Trading (MT5)")
    print("=" * 80)
    
    # Uncomment when ready:
    """
    import MetaTrader5 as mt5
    import time
    
    # Initialize MT5
    if not mt5.initialize():
        print("❌ Failed to initialize MetaTrader 5")
        return
    
    # Login to your account
    login = YOUR_LOGIN_NUMBER
    password = "YOUR_PASSWORD"
    server = "YOUR_BROKER_SERVER"
    
    if not mt5.login(login, password, server):
        print(f"❌ Failed to login to MT5: {mt5.last_error()}")
        mt5.shutdown()
        return
    
    print(f"✅ Connected to MT5: {mt5.account_info().login}")
    
    # Initialize bot
    bot = ICTTradingBot()
    
    # Main trading loop
    try:
        while True:
            print(f"\n{'='*80}")
            print(f"Fetching data at {datetime.now()}")
            print(f"{'='*80}")
            
            # Fetch multi-timeframe data
            data = {
                'daily': fetch_mt5_data(SYMBOL, mt5.TIMEFRAME_D1, 100),
                '4h': fetch_mt5_data(SYMBOL, mt5.TIMEFRAME_H4, 200),
                '1h': fetch_mt5_data(SYMBOL, mt5.TIMEFRAME_H1, 500),
                '15m': fetch_mt5_data(SYMBOL, mt5.TIMEFRAME_M15, 1000),
                '5m': fetch_mt5_data(SYMBOL, mt5.TIMEFRAME_M5, 2000)
            }
            
            # Verify all data loaded
            if all(df is not None and len(df) > 0 for df in data.values()):
                # Run strategy
                bot.run_strategy(data)
            else:
                print("⚠️  Failed to load some data, skipping iteration...")
            
            # Wait 5 minutes before next check
            print(f"\nWaiting 5 minutes before next iteration...")
            time.sleep(300)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Bot stopped by user")
    
    finally:
        # Cleanup
        mt5.shutdown()
        print("✅ MT5 connection closed")
    """
    
    print("\n⚠️  MT5 integration not configured.")
    print("    Uncomment and configure the code in this function.")


def backtest_mode():
    """
    Run backtest on historical data
    
    This would load historical data and test the strategy.
    """
    print("=" * 80)
    print("ICT XAUUSD Trading Bot - Backtest Mode")
    print("=" * 80)
    print("\n⚠️  Backtest mode not yet implemented.")
    print("    This would load historical data and test the strategy.")
    print("\nTo implement:")
    print("  1. Load historical OHLC data (CSV, database, or API)")
    print("  2. Iterate through bars")
    print("  3. Run strategy on each bar")
    print("  4. Track performance statistics")
    print("  5. Generate report with charts")


def main():
    """Main entry point"""
    print("\n" + "=" * 80)
    print(" " * 20 + "ICT XAUUSD TRADING BOT")
    print("=" * 80)
    print("\nSelect mode:")
    print("  1. Run with SAMPLE data (demonstration)")
    print("  2. Run with MT5 LIVE data (requires MT5 setup)")
    print("  3. Backtest mode (not yet implemented)")
    print("  0. Exit")
    print()
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == '1':
        run_bot_with_sample_data()
    elif choice == '2':
        run_bot_with_mt5_data()
    elif choice == '3':
        backtest_mode()
    elif choice == '0':
        print("Exiting...")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
