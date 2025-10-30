"""
Test Installation Script
Verify that all components are properly installed and working
"""

import sys
import importlib
from pathlib import Path


def test_python_version():
    """Test Python version"""
    print("Testing Python version...")
    version = sys.version_info
    
    if version.major >= 3 and version.minor >= 8:
        print(f"  ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ❌ Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)")
        return False


def test_dependencies():
    """Test required dependencies"""
    print("\nTesting dependencies...")
    
    required_packages = [
        'pandas',
        'numpy',
        'scipy'
    ]
    
    optional_packages = [
        ('MetaTrader5', 'MetaTrader 5 integration'),
        ('yfinance', 'Yahoo Finance data'),
        ('ta', 'Technical analysis'),
    ]
    
    all_passed = True
    
    # Test required
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} (REQUIRED)")
            all_passed = False
    
    # Test optional
    for package, description in optional_packages:
        try:
            importlib.import_module(package)
            print(f"  ✅ {package} ({description})")
        except ImportError:
            print(f"  ⚠️  {package} - not installed ({description})")
    
    return all_passed


def test_modules():
    """Test custom modules"""
    print("\nTesting custom modules...")
    
    modules = [
        'config',
        'market_structure',
        'liquidity',
        'order_blocks_fvg',
        'fibonacci_ote',
        'session_filter',
        'quant_filters',
        'risk_management',
        'trading_bot',
        'utils',
        'data_fetcher'
    ]
    
    all_passed = True
    
    for module in modules:
        try:
            importlib.import_module(module)
            print(f"  ✅ {module}.py")
        except Exception as e:
            print(f"  ❌ {module}.py - Error: {e}")
            all_passed = False
    
    return all_passed


def test_directories():
    """Test required directories"""
    print("\nTesting directory structure...")
    
    directories = ['logs', 'data', 'charts', 'models']
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(exist_ok=True)
            print(f"  ✅ Created {directory}/")
        else:
            print(f"  ✅ {directory}/")
    
    return True


def test_trading_bot_initialization():
    """Test trading bot initialization"""
    print("\nTesting trading bot initialization...")
    
    try:
        from trading_bot import ICTTradingBot
        
        bot = ICTTradingBot()
        print("  ✅ Trading bot initialized successfully")
        
        # Test components
        if hasattr(bot, 'market_structure'):
            print("  ✅ Market structure analyzer loaded")
        if hasattr(bot, 'liquidity_analyzer'):
            print("  ✅ Liquidity analyzer loaded")
        if hasattr(bot, 'ob_analyzer'):
            print("  ✅ Order block analyzer loaded")
        if hasattr(bot, 'fvg_analyzer'):
            print("  ✅ FVG analyzer loaded")
        if hasattr(bot, 'fibonacci'):
            print("  ✅ Fibonacci OTE loaded")
        if hasattr(bot, 'risk_manager'):
            print("  ✅ Risk manager loaded")
        
        return True
    
    except Exception as e:
        print(f"  ❌ Failed to initialize trading bot: {e}")
        return False


def test_data_generation():
    """Test sample data generation"""
    print("\nTesting data generation...")
    
    try:
        from example_usage import generate_sample_data
        import pandas as pd
        
        df = generate_sample_data('XAUUSD', '1H', 100)
        
        if isinstance(df, pd.DataFrame) and len(df) > 0:
            print(f"  ✅ Generated {len(df)} bars of sample data")
            
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if all(col in df.columns for col in required_cols):
                print("  ✅ All required columns present")
                return True
            else:
                print("  ❌ Missing required columns")
                return False
        else:
            print("  ❌ Failed to generate data")
            return False
    
    except Exception as e:
        print(f"  ❌ Error generating data: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 80)
    print(" " * 20 + "ICT XAUUSD TRADING BOT")
    print(" " * 25 + "Installation Test")
    print("=" * 80)
    
    results = []
    
    results.append(("Python Version", test_python_version()))
    results.append(("Dependencies", test_dependencies()))
    results.append(("Custom Modules", test_modules()))
    results.append(("Directories", test_directories()))
    results.append(("Bot Initialization", test_trading_bot_initialization()))
    results.append(("Data Generation", test_data_generation()))
    
    print("\n" + "=" * 80)
    print(" " * 30 + "TEST SUMMARY")
    print("=" * 80)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:.<40} {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 80)
    
    if all_passed:
        print("🎉 All tests passed! The system is ready to use.")
        print("\nNext steps:")
        print("  1. Configure your broker API in config.py")
        print("  2. Run: python example_usage.py")
        print("  3. Test with sample data before going live")
    else:
        print("⚠️  Some tests failed. Please fix the issues before proceeding.")
        print("\nCommon solutions:")
        print("  - Install missing packages: pip install -r requirements.txt")
        print("  - Check Python version (3.8+ required)")
        print("  - Verify all module files are present")
    
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
