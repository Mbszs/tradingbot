"""
Session Timing Filter Module
Filters trades based on trading session (Asia, London, New York)
"""

import pandas as pd
from datetime import datetime, time
from typing import Dict, Optional
from enum import Enum


class TradingSession(Enum):
    """Trading session types"""
    ASIA = "asia"
    LONDON = "london"
    NEWYORK = "newyork"
    CLOSED = "closed"


class SessionFilter:
    """
    Filters trading based on session timing
    
    Sessions (GMT):
    - Asia: 23:00 - 06:00
    - London: 07:00 - 11:00
    - New York: 12:00 - 20:00 (disabled by default per strategy)
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.sessions = config.get('SESSIONS', {})
    
    def get_current_session(self, timestamp: pd.Timestamp) -> TradingSession:
        """
        Determine which trading session a timestamp falls into
        
        Args:
            timestamp: pandas Timestamp to check
            
        Returns:
            TradingSession enum
        """
        # Convert to GMT time
        if timestamp.tz is None:
            current_time = timestamp.time()
        else:
            current_time = timestamp.tz_convert('GMT').time()
        
        # Check each session
        for session_name, session_info in self.sessions.items():
            if not session_info.get('enabled', True):
                continue
            
            start_time = self._parse_time(session_info['start'])
            end_time = self._parse_time(session_info['end'])
            
            # Handle sessions that cross midnight
            if start_time > end_time:
                if current_time >= start_time or current_time <= end_time:
                    return TradingSession[session_name.upper()]
            else:
                if start_time <= current_time <= end_time:
                    return TradingSession[session_name.upper()]
        
        return TradingSession.CLOSED
    
    def is_trading_allowed(self, timestamp: pd.Timestamp) -> bool:
        """
        Check if trading is allowed at given timestamp
        
        Args:
            timestamp: pandas Timestamp to check
            
        Returns:
            True if trading is allowed, False otherwise
        """
        session = self.get_current_session(timestamp)
        
        if session == TradingSession.CLOSED:
            return False
        
        # Check if session is enabled in config
        session_name = session.value.upper()
        if session_name in self.sessions:
            return self.sessions[session_name].get('enabled', True)
        
        return False
    
    def get_session_info(self, timestamp: pd.Timestamp) -> Dict:
        """
        Get detailed session information for a timestamp
        
        Args:
            timestamp: pandas Timestamp to check
            
        Returns:
            Dictionary with session details
        """
        session = self.get_current_session(timestamp)
        
        return {
            'session': session,
            'session_name': session.value,
            'trading_allowed': self.is_trading_allowed(timestamp),
            'timestamp': timestamp
        }
    
    def filter_dataframe_by_session(self, df: pd.DataFrame, 
                                   sessions: Optional[list] = None) -> pd.DataFrame:
        """
        Filter DataFrame to only include rows from specified sessions
        
        Args:
            df: DataFrame with DatetimeIndex
            sessions: List of TradingSession enums (None = all enabled sessions)
            
        Returns:
            Filtered DataFrame
        """
        if sessions is None:
            # Use all enabled sessions
            sessions = [TradingSession[s.upper()] 
                       for s, info in self.sessions.items() 
                       if info.get('enabled', True)]
        
        # Create mask for valid session times
        mask = df.index.map(lambda ts: self.get_current_session(ts) in sessions)
        
        return df[mask]
    
    def get_next_session_open(self, current_time: pd.Timestamp) -> pd.Timestamp:
        """
        Get the timestamp of next session open
        
        Args:
            current_time: Current timestamp
            
        Returns:
            Timestamp of next session open
        """
        # Find next enabled session
        session_times = []
        
        for session_name, session_info in self.sessions.items():
            if session_info.get('enabled', True):
                start_time = self._parse_time(session_info['start'])
                session_times.append((session_name, start_time))
        
        # Sort by time
        session_times.sort(key=lambda x: x[1])
        
        current_time_only = current_time.time()
        
        # Find next session
        for session_name, start_time in session_times:
            if start_time > current_time_only:
                next_open = current_time.replace(
                    hour=start_time.hour,
                    minute=start_time.minute,
                    second=0,
                    microsecond=0
                )
                return next_open
        
        # If no session found today, return first session tomorrow
        first_session_time = session_times[0][1]
        next_open = current_time.replace(
            hour=first_session_time.hour,
            minute=first_session_time.minute,
            second=0,
            microsecond=0
        ) + pd.Timedelta(days=1)
        
        return next_open
    
    def _parse_time(self, time_str: str) -> time:
        """
        Parse time string to time object
        
        Args:
            time_str: Time string in format 'HH:MM'
            
        Returns:
            datetime.time object
        """
        hour, minute = map(int, time_str.split(':'))
        return time(hour=hour, minute=minute)
    
    def is_session_open(self, timestamp: pd.Timestamp) -> bool:
        """
        Check if any trading session is currently open
        
        Args:
            timestamp: Timestamp to check
            
        Returns:
            True if a session is open
        """
        return self.get_current_session(timestamp) != TradingSession.CLOSED
