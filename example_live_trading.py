"""
Example Live/Paper Trading Script
Demonstrates how to run the XAU/USD trading bot in live or paper trading mode
"""

from config import TradingConfig
from trading_bot import XAUUSDTradingBot
import logging
import os


def setup_live_trading():
    """
    Setup and run live trading bot
    
    IMPORTANT: Before running in live mode:
    1. Implement data loading in trading_bot.py::load_historical_data()
    2. Implement trade execution in trading_bot.py::execute_trade()
    3. Implement trade closing in trading_bot.py::close_trade()
    4. Test thoroughly in paper trading mode first!
    """
    
    print("="*70)
    print("XAU/USD Trading Bot - Live/Paper Trading")
    print("="*70)
    print()
    
    # Create necessary directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('results', exist_ok=True)
    
    # Initialize configuration
    config = TradingConfig()
    
    # Display current configuration
    print("Current Configuration:")
    print(f"  Symbol:           {config.SYMBOL}")
    print(f"  Entry Timeframe:  {config.TIMEFRAME_ENTRY}")
    print(f"  HTF Timeframe:    {config.TIMEFRAME_HTF}")
    print(f"  Risk per Trade:   {config.RISK_PER_TRADE*100}%")
    print(f"  Stop Loss:        {config.STOP_LOSS_ATR} ATR")
    print(f"  Max Open Trades:  {config.MAX_OPEN_TRADES}")
    print(f"  Session Filter:   {'Enabled' if config.ENABLE_SESSION_FILTER else 'Disabled'}")
    print()
    
    # Ask user for mode
    print("Trading Modes:")
    print("1. Paper Trading (Recommended for testing)")
    print("2. Live Trading (Real money - USE WITH CAUTION)")
    print()
    
    mode_choice = input("Select mode (1 or 2): ").strip()
    
    if mode_choice == '2':
        print("\n" + "!"*70)
        print("WARNING: LIVE TRADING MODE SELECTED")
        print("!"*70)
        print("\nThis will execute REAL trades with REAL money!")
        print("\nBefore proceeding, ensure:")
        print("  ✓ You have thoroughly backtested the strategy")
        print("  ✓ You have paper traded successfully for at least 1 month")
        print("  ✓ You have implemented broker connection in trading_bot.py")
        print("  ✓ You understand the risks of automated trading")
        print("  ✓ You are starting with a small account or test account")
        print()
        
        confirm = input("Type 'I UNDERSTAND THE RISKS' to continue: ").strip()
        
        if confirm != 'I UNDERSTAND THE RISKS':
            print("\nLive trading cancelled. Good choice - always test first!")
            return
        
        live_mode = True
        print("\nInitializing LIVE TRADING mode...")
    else:
        live_mode = False
        print("\nInitializing PAPER TRADING mode...")
    
    # Get initial capital
    print()
    capital_input = input("Enter initial capital (default 10000): ").strip()
    initial_capital = float(capital_input) if capital_input else 10000.0
    
    print()
    print("="*70)
    
    # Initialize bot
    bot = XAUUSDTradingBot(
        config=config,
        initial_capital=initial_capital,
        live_mode=live_mode
    )
    
    print()
    print("Bot initialized successfully!")
    print()
    print("Trading Configuration:")
    print(f"  Mode:             {'LIVE' if live_mode else 'PAPER'}")
    print(f"  Initial Capital:  ${initial_capital:,.2f}")
    print(f"  Update Interval:  {get_update_interval(config.TIMEFRAME_ENTRY)}s")
    print()
    
    # Determine update interval based on timeframe
    update_interval = get_update_interval(config.TIMEFRAME_ENTRY)
    
    print("="*70)
    print("STARTING TRADING BOT")
    print("="*70)
    print()
    print("The bot will now:")
    print("  1. Load market data")
    print("  2. Analyze market structure and ICT concepts")
    print("  3. Generate trading signals when conditions are met")
    print("  4. Manage open positions")
    print(f"  5. Update every {update_interval} seconds")
    print()
    print("Press Ctrl+C to stop the bot safely")
    print()
    print("="*70)
    
    try:
        # Run the bot
        bot.run(update_interval=update_interval)
        
    except KeyboardInterrupt:
        print("\n\nBot stopped by user")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        logging.exception("Fatal error in bot")
    finally:
        # Print final statistics
        print("\n" + "="*70)
        print("FINAL STATISTICS")
        print("="*70)
        
        stats = bot.risk_manager.get_statistics()
        
        print(f"\nCapital:")
        print(f"  Initial:  ${initial_capital:,.2f}")
        print(f"  Final:    ${stats['final_capital']:,.2f}")
        print(f"  Return:   {stats['total_return']*100:.2f}%")
        
        print(f"\nTrades:")
        print(f"  Total:    {stats['total_trades']}")
        print(f"  Winning:  {stats['winning_trades']}")
        print(f"  Losing:   {stats['losing_trades']}")
        print(f"  Win Rate: {stats['win_rate']*100:.1f}%")
        
        print(f"\nPerformance:")
        print(f"  Profit Factor: {stats['profit_factor']:.2f}")
        print(f"  Avg Win:       ${stats['avg_win']:.2f}")
        print(f"  Avg Loss:      ${stats['avg_loss']:.2f}")
        print(f"  Max Drawdown:  {stats['max_drawdown']*100:.2f}%")
        
        print("\n" + "="*70)
        print("Thank you for using the XAU/USD Trading Bot!")
        print("="*70)


def get_update_interval(timeframe: str) -> int:
    """Get update interval in seconds based on timeframe"""
    intervals = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400
    }
    return intervals.get(timeframe, 3600)


def run_single_iteration_test():
    """
    Run a single iteration test to verify bot setup
    Useful for debugging and testing your data connection
    """
    print("="*70)
    print("Single Iteration Test")
    print("="*70)
    print()
    print("This will run the bot once to test your setup")
    print()
    
    config = TradingConfig()
    bot = XAUUSDTradingBot(config, initial_capital=10000, live_mode=False)
    
    print("Running single iteration...")
    print()
    
    try:
        bot.run_once()
        print()
        print("="*70)
        print("Test completed successfully!")
        print("="*70)
        print()
        print("If you see any errors above, fix them before running live.")
        print("Common issues:")
        print("  - Data loading not implemented")
        print("  - Insufficient historical data")
        print("  - Broker connection issues")
        
    except Exception as e:
        print()
        print("="*70)
        print("ERROR DURING TEST")
        print("="*70)
        print(f"\nError: {e}")
        print()
        print("Please fix the error before running the bot continuously.")
        logging.exception("Test iteration failed")


def monitor_bot_performance():
    """
    Simple monitoring script to check bot status
    Useful for running alongside the bot
    """
    import time
    import json
    from datetime import datetime
    
    print("="*70)
    print("Bot Performance Monitor")
    print("="*70)
    print()
    print("This will monitor the bot's performance in real-time")
    print("Make sure the bot is running in another terminal")
    print()
    print("Press Ctrl+C to stop monitoring")
    print()
    
    # In a real implementation, you would:
    # 1. Read from a shared state file or database
    # 2. Connect to the bot's API/socket
    # 3. Parse log files
    
    print("Note: This is a placeholder - implement your monitoring logic")
    print("Suggestions:")
    print("  - Read from logs/trading_bot.log")
    print("  - Parse results/daily_stats.json")
    print("  - Connect to a monitoring dashboard")
    print()


if __name__ == "__main__":
    import sys
    
    print("\n" + "="*70)
    print("XAU/USD Trading Bot - Live Trading Examples")
    print("="*70)
    print()
    print("Select an option:")
    print("1. Run live/paper trading bot")
    print("2. Run single iteration test (debugging)")
    print("3. Monitor bot performance")
    print()
    
    choice = input("Enter choice (1/2/3) or press Enter for option 1: ").strip()
    
    if choice == '2':
        run_single_iteration_test()
    elif choice == '3':
        monitor_bot_performance()
    else:
        setup_live_trading()
