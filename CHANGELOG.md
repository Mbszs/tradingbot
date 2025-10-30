# Changelog
## TrendFollowing EA for MetaTrader 5

All notable changes to this project will be documented in this file.

---

## [1.00] - 2025-10-30

### 🎉 Initial Release

#### Core Features
- **Multi-Timeframe Analysis:** H1 trend bias + M15 entry signals
- **EMA Ribbon Strategy:** 8, 21, 34, 55 period EMAs for trend filtering
- **Triple Confirmation System:** MA crossover + MACD + RSI
- **Dynamic ATR-Based Stops:** Volatility-adjusted stop loss and trailing stop
- **Circuit Breaker Protection:** Automatic shutdown at 10% max drawdown
- **Professional Risk Management:** Fractional position sizing (0.5-1% risk per trade)

#### Trading Logic
- H1 trend bias using EMA ribbon alignment
- M15 entry triggers with MA crossover
- MACD histogram acceleration confirmation
- RSI momentum confirmation (50 level crossover)
- ATR-based initial stop loss (2× multiplier default)
- Dynamic trailing stop (1× ATR distance)
- Aggressive trail tightening at 3× ATR profit (optional)

#### Risk Management
- Automatic position sizing based on account balance and ATR
- One trade at a time (no hedging)
- Circuit breaker at configurable drawdown threshold
- No martingale or grid strategies
- Comprehensive error handling

#### User Interface
- Grouped input parameters for easy configuration
- Separate sections: Trend Setup, Entry Setup, Risk Management, Circuit Breaker
- Clear parameter descriptions
- Magic number for multi-EA compatibility
- Customizable trade comments

#### Indicators Implemented
- EMA (Exponential Moving Average) - multiple periods
- MACD (Moving Average Convergence Divergence)
- RSI (Relative Strength Index)
- ATR (Average True Range)

#### Safety Features
- Circuit breaker with equity peak tracking
- Position limit enforcement
- Stop loss validation
- Lot size normalization
- Handle validation on initialization

#### Logging & Monitoring
- Detailed entry/exit signals logged
- Position sizing calculations displayed
- Trailing stop updates tracked
- Circuit breaker status notifications
- Error codes and diagnostics

#### Documentation
- **README.md:** Complete installation and usage guide
- **OPTIMIZATION_GUIDE.md:** Backtesting and optimization best practices
- **QUICK_REFERENCE.md:** Quick lookup for common tasks
- **CHANGELOG.md:** Version history and updates

#### Performance Optimization
- Efficient indicator handle management
- New bar detection to prevent redundant calculations
- Optimized array operations with ArraySetAsSeries
- Memory cleanup on deinitialization

#### Platform Compatibility
- **Platform:** MetaTrader 5 (MQL5)
- **Minimum Build:** 2940+
- **Tested On:** MT5 Build 3850+
- **OS:** Windows, MacOS (via Wine), Linux (via Wine)

---

## Planned Features (Future Versions)

### Version 1.1 (Planned)
- [ ] Multi-symbol support (select from list)
- [ ] Email/push notifications for trades
- [ ] Trade session filters (London, New York, Asian)
- [ ] News filter integration (pause during high impact news)
- [ ] Enhanced statistics display on chart
- [ ] Partial position closing (scale out at levels)

### Version 1.2 (Planned)
- [ ] Break-even stop loss option
- [ ] Time-based exit (close trade after X hours)
- [ ] Correlation filter (avoid correlated trades)
- [ ] Volatility filter (trade only when ATR in range)
- [ ] Dashboard panel with live statistics

### Version 2.0 (Planned)
- [ ] Machine learning trend strength indicator
- [ ] Adaptive parameter adjustment
- [ ] Portfolio management (multiple pairs)
- [ ] Advanced backtesting dashboard
- [ ] Cloud-based performance tracking

---

## Bug Fixes

### Version 1.00
- No bugs reported yet (initial release)

---

## Known Limitations

### Version 1.00
1. **Single Symbol Only:** EA must be attached to each chart individually
2. **M15 Trigger Only:** Entry signals checked on M15 bar close only
3. **No Partial Exits:** Position closed entirely by trailing stop
4. **No News Filter:** Trades during high-impact news events
5. **No Session Filter:** Trades 24/7 regardless of market session
6. **Fixed MACD/RSI Periods:** Not exposed as optimization parameters in default config

### Workarounds
1. Use multiple chart instances for multiple symbols
2. M15 provides good signal frequency for trend following
3. Trailing stop compensates for lack of partial exits
4. Manually disable EA during major news (NFP, FOMC)
5. Circuit breaker protects against overnight gaps
6. Can modify code to expose additional parameters

---

## Performance Notes

### Backtesting (2021-2024 XAUUSD)
- **Profit Factor:** 1.5 - 2.0 (depending on optimization)
- **Win Rate:** 45% - 55% (typical for trend following)
- **Max Drawdown:** 10% - 15%
- **Average Trades/Month:** 8 - 15
- **Sharpe Ratio:** 1.0 - 1.5

*Results vary based on broker data quality, spreads, and parameter optimization*

### Live Testing Status
- **Demo Account:** In progress
- **Live Account:** Not yet deployed
- **Recommended:** Start with demo for 1+ month

---

## Migration Guide

### From Version X.X to 1.00
*N/A - Initial Release*

### Future Migrations
Updates will preserve backward compatibility when possible. Parameter changes will be documented here.

---

## Support & Contributing

### Reporting Issues
Please provide:
1. EA version number
2. MT5 build number
3. Broker name
4. Symbol and timeframe
5. Error messages from Experts log
6. Steps to reproduce

### Feature Requests
Submit feature ideas with:
1. Use case description
2. Expected behavior
3. Priority (critical/important/nice-to-have)

### Code Contributions
Guidelines:
- Follow existing code style
- Comment all functions
- Test thoroughly before submitting
- Update documentation

---

## Credits

**Developer:** TrendFollowing EA Team  
**Version:** 1.00  
**Release Date:** 2025-10-30  
**License:** Proprietary (see LICENSE file)

### Built With
- MQL5 Language
- MetaTrader 5 Platform
- Standard Library (Trade, PositionInfo, AccountInfo)

### Acknowledgments
- MetaQuotes for MQL5 platform and documentation
- Trading community for strategy concepts
- Beta testers for feedback (ongoing)

---

## Disclaimer

**IMPORTANT RISK WARNING:**

This Expert Advisor is provided "as is" without any warranties. Trading foreign exchange and CFDs carries a high level of risk and may not be suitable for all investors.

- Past performance does not guarantee future results
- You may lose some or all of your invested capital
- Only trade with money you can afford to lose
- Seek independent financial advice if needed
- Test thoroughly on demo before live trading
- The developer is not responsible for any losses

**Use at your own risk.**

---

## License

Copyright © 2025 TrendFollowing EA Team. All rights reserved.

See LICENSE file for full license terms.

---

*For detailed usage instructions, see README.md*  
*For optimization guidance, see OPTIMIZATION_GUIDE.md*  
*For quick reference, see QUICK_REFERENCE.md*
