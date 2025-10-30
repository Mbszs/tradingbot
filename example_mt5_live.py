"""
MT5 Live Trading Example
Run the trading bot with MetaTrader 5
"""

from config import TradingConfig
from trading_bot_mt5 import XAUUSDTradingBotMT5
from mt5_connector import MT5Connector
import logging
import os


def setup_mt5_live_trading():
    """Setup and run MT5 live trading bot"""
    
    print("="*70)
    print("XAU/USD Trading Bot - MT5 Live/Paper Trading")
    print("="*70)
    print()
    
    # Create directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('results', exist_ok=True)
    
    # Connect to MT5
    print("Step 1: Connecting to MetaTrader 5...")
    print("-" * 70)
    
    mt5 = MT5Connector(symbol="XAUUSD", magic_number=234000)
    
    # Try to connect
    if not mt5.connect():
        print("\n❌ Failed to connect to MT5")
        print("\nTroubleshooting:")
        print("  1. Make sure MetaTrader 5 terminal is running")
        print("  2. Ensure you are logged into your trading account")
        print("  3. Check that XAUUSD is available in Market Watch")
        print("  4. Try running MT5 as administrator")
        print()
        
        retry = input("Try to connect again? (y/n): ").strip().lower()
        if retry == 'y':
            if not mt5.connect():
                print("Still failed to connect. Please check MT5 and try again.")
                return
        else:
            return
    
    print("✓ MT5 Connected Successfully!\n")
    
    # Display account info
    account = mt5.get_account_info()
    symbol_info = mt5.get_symbol_info()
    
    print("Account Information:")
    print("-" * 70)
    print(f"  Balance:      ${account['balance']:,.2f}")
    print(f"  Equity:       ${account['equity']:,.2f}")
    print(f"  Free Margin:  ${account['free_margin']:,.2f}")
    print(f"  Leverage:     1:{account['leverage']}")
    print(f"  Currency:     {account['currency']}")
    print()
    
    print("Symbol Information (XAUUSD):")
    print("-" * 70)
    print(f"  Spread:       {symbol_info['spread']} points")
    print(f"  Min Volume:   {symbol_info['volume_min']}")
    print(f"  Max Volume:   {symbol_info['volume_max']}")
    print(f"  Volume Step:  {symbol_info['volume_step']}")
    print()
    
    # Check for existing positions
    existing_positions = mt5.get_open_positions()
    if existing_positions:
        print(f"⚠️  Warning: {len(existing_positions)} existing position(s) found")
        print("These will be tracked by the bot.")
        for pos in existing_positions:
            print(f"  - {pos['type'].upper()} {pos['volume']} lots @ ${pos['price_open']:.2f}")
        print()
    
    # Configuration
    print("Step 2: Trading Configuration")
    print("-" * 70)
    
    config = TradingConfig()
    
    print(f"  Symbol:           {config.SYMBOL}")
    print(f"  Entry Timeframe:  {config.TIMEFRAME_ENTRY}")
    print(f"  HTF Timeframe:    {config.TIMEFRAME_HTF}")
    print(f"  Risk per Trade:   {config.RISK_PER_TRADE*100}%")
    print(f"  Stop Loss:        {config.STOP_LOSS_ATR} ATR")
    print(f"  Max Open Trades:  {config.MAX_OPEN_TRADES}")
    print(f"  Session Filter:   {'Enabled' if config.ENABLE_SESSION_FILTER else 'Disabled'}")
    print()
    
    modify = input("Modify configuration? (y/n): ").strip().lower()
    if modify == 'y':
        try:
            risk_input = input(f"Risk per trade % (current: {config.RISK_PER_TRADE*100}): ").strip()
            if risk_input:
                config.RISK_PER_TRADE = float(risk_input) / 100
            
            sl_input = input(f"Stop loss ATR (current: {config.STOP_LOSS_ATR}): ").strip()
            if sl_input:
                config.STOP_LOSS_ATR = float(sl_input)
            
            max_trades_input = input(f"Max open trades (current: {config.MAX_OPEN_TRADES}): ").strip()
            if max_trades_input:
                config.MAX_OPEN_TRADES = int(max_trades_input)
            
            print("\n✓ Configuration updated\n")
        except ValueError:
            print("Invalid input, using default configuration\n")
    
    # Trading Mode Selection
    print("Step 3: Select Trading Mode")
    print("-" * 70)
    print("1. Paper Trading (Recommended - Simulated trades, no risk)")
    print("2. Live Trading (Real trades with real money)")
    print()
    
    mode = input("Select mode (1 or 2): ").strip()
    
    if mode == '2':
        # Live trading confirmation
        print("\n" + "!"*70)
        print("⚠️  LIVE TRADING MODE SELECTED ⚠️")
        print("!"*70)
        print("\nYou are about to enable LIVE TRADING with REAL MONEY!")
        print("\n📋 Pre-flight Checklist:")
        print("  ☐ Have you backtested thoroughly (2+ years)?")
        print("  ☐ Have you paper traded successfully (1+ month)?")
        print("  ☐ Do you understand the strategy completely?")
        print("  ☐ Are you starting with capital you can afford to lose?")
        print("  ☐ Have you set appropriate risk parameters?")
        print("  ☐ Will you monitor the bot regularly?")
        print()
        
        confirm1 = input("I have completed the checklist above (yes/no): ").strip().lower()
        if confirm1 != 'yes':
            print("\n✓ Good decision. Start with paper trading first!")
            mode = '1'
        else:
            print()
            confirm2 = input("Type 'START LIVE TRADING' to confirm: ").strip()
            if confirm2 != 'START LIVE TRADING':
                print("\n✓ Live trading cancelled. Using paper trading mode.")
                mode = '1'
    
    live_mode = (mode == '2')
    
    # Update interval
    print("\nStep 4: Update Interval")
    print("-" * 70)
    intervals = {
        '1h': 3600,
        '30m': 1800,
        '15m': 900,
        '5m': 300
    }
    
    default_interval = intervals.get(config.TIMEFRAME_ENTRY, 3600)
    
    print(f"Recommended: {default_interval}s ({config.TIMEFRAME_ENTRY})")
    interval_input = input(f"Update interval in seconds (default {default_interval}): ").strip()
    update_interval = int(interval_input) if interval_input else default_interval
    
    # Final confirmation
    print("\n" + "="*70)
    print("FINAL CONFIGURATION")
    print("="*70)
    print(f"  Mode:             {'🔴 LIVE TRADING' if live_mode else '📝 PAPER TRADING'}")
    print(f"  Account Balance:  ${account['balance']:,.2f}")
    print(f"  Risk per Trade:   {config.RISK_PER_TRADE*100}%")
    print(f"  Update Interval:  {update_interval}s")
    print(f"  Max Positions:    {config.MAX_OPEN_TRADES}")
    print("="*70)
    print()
    
    start = input("Start trading bot? (y/n): ").strip().lower()
    
    if start != 'y':
        print("\n✓ Trading cancelled")
        mt5.disconnect()
        return
    
    # Initialize bot
    print("\n" + "="*70)
    print("INITIALIZING TRADING BOT")
    print("="*70)
    print()
    
    bot = XAUUSDTradingBotMT5(
        config=config,
        mt5_connector=mt5,
        live_mode=live_mode
    )
    
    print("✓ Bot initialized successfully!")
    print()
    print("="*70)
    print("🤖 TRADING BOT STARTED")
    print("="*70)
    print()
    print(f"Mode: {'🔴 LIVE' if live_mode else '📝 PAPER'}")
    print(f"Time: {update_interval}s intervals")
    print()
    print("The bot is now running. It will:")
    print("  ✓ Monitor XAU/USD market continuously")
    print("  ✓ Analyze market structure and ICT concepts")
    print("  ✓ Generate signals when conditions align")
    print("  ✓ Manage positions with dynamic risk")
    print("  ✓ Log all activities to logs/trading_bot_mt5.log")
    print()
    print("📊 Check status in the terminal output")
    print("📝 View detailed logs in logs/ folder")
    print("💾 Results will be saved in results/ folder")
    print()
    print("⚠️  Press Ctrl+C to stop the bot safely")
    print()
    print("="*70)
    
    try:
        # Run the bot
        bot.run(update_interval=update_interval)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Bot stopped by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        logging.exception("Fatal error")
    finally:
        print("\n" + "="*70)
        print("SHUTDOWN SUMMARY")
        print("="*70)
        
        # Final stats
        account = mt5.get_account_info()
        stats = bot.risk_manager.get_statistics()
        
        print(f"\nAccount Status:")
        print(f"  Balance:  ${account['balance']:,.2f}")
        print(f"  Equity:   ${account['equity']:,.2f}")
        print(f"  Profit:   ${account['profit']:+,.2f}")
        
        print(f"\nTrading Statistics:")
        print(f"  Total Trades:   {stats['total_trades']}")
        print(f"  Winning:        {stats['winning_trades']}")
        print(f"  Losing:         {stats['losing_trades']}")
        print(f"  Win Rate:       {stats['win_rate']*100:.1f}%")
        print(f"  Profit Factor:  {stats['profit_factor']:.2f}")
        print(f"  Max Drawdown:   {stats['max_drawdown']*100:.1f}%")
        
        print("\n" + "="*70)
        print("Thank you for using the XAU/USD Trading Bot!")
        print("="*70)
        
        mt5.disconnect()


def test_mt5_connection():
    """Test MT5 connection and display info"""
    print("="*70)
    print("MT5 Connection Test")
    print("="*70)
    print()
    
    mt5 = MT5Connector(symbol="XAUUSD")
    
    print("Attempting to connect to MT5...")
    if not mt5.connect():
        print("❌ Connection failed")
        return
    
    print("✓ Connected successfully!\n")
    
    # Account info
    account = mt5.get_account_info()
    print("Account Information:")
    print(f"  Balance:   ${account['balance']:,.2f}")
    print(f"  Equity:    ${account['equity']:,.2f}")
    print(f"  Leverage:  1:{account['leverage']}")
    print()
    
    # Symbol info
    symbol = mt5.get_symbol_info()
    print("Symbol Information (XAUUSD):")
    print(f"  Spread:    {symbol['spread']} points")
    print(f"  Min Lot:   {symbol['volume_min']}")
    print(f"  Max Lot:   {symbol['volume_max']}")
    print()
    
    # Current price
    price = mt5.get_current_price()
    print("Current Price:")
    print(f"  Bid:       ${price['bid']:.2f}")
    print(f"  Ask:       ${price['ask']:.2f}")
    print(f"  Spread:    ${price['spread']:.2f}")
    print()
    
    # Get recent data
    print("Testing data retrieval...")
    df = mt5.get_historical_data('1h', bars=10)
    if not df.empty:
        print("✓ Data retrieved successfully")
        print(f"  Last 1H candle: ${df['close'].iloc[-1]:.2f}")
        print(f"  Date: {df.index[-1]}")
    else:
        print("❌ Failed to retrieve data")
    
    print()
    mt5.disconnect()
    print("✓ Test complete")


if __name__ == "__main__":
    print("\nMT5 Trading Bot Options:")
    print("1. Run live/paper trading bot")
    print("2. Test MT5 connection")
    print()
    
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == '2':
        test_mt5_connection()
    else:
        setup_mt5_live_trading()
