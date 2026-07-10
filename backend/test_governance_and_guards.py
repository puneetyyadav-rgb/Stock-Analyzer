import os
import sys
import json
import unittest
import pandas as pd
from datetime import datetime, timedelta

# Ensure backend directory is in path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import qlib_service as qs


class TestGovernanceAndGuards(unittest.TestCase):
    def test_01_t1_completed_bar_guard(self):
        """Verifies that clean_ohlcv_completed_bars drops today's partial intraday bar before market close 15:30 IST."""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        # Create a mock dataframe with yesterday's closing bar AND today's intraday bar
        df = pd.DataFrame({
            "Open": [100.0, 105.0],
            "High": [106.0, 107.0],
            "Low": [99.0, 104.0],
            "Close": [105.0, 106.0],
            "Volume": [1000000.0, 200000.0]
        }, index=pd.to_datetime([yesterday.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")]))

        cleaned_df, guard_info = qs.clean_ohlcv_completed_bars(df)
        
        target_close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        if now < target_close_time:
            self.assertTrue(guard_info["excluded_current_session"], "T-1 Guard should exclude partial intraday bar before 15:30 IST!")
            self.assertEqual(len(cleaned_df), 1, "Dataframe length should be trimmed by 1 row!")
            self.assertEqual(pd.to_datetime(cleaned_df.index[-1]).date(), yesterday.date(), "Last bar must equal T-1 completed day!")
        else:
            self.assertFalse(guard_info["excluded_current_session"], "Post-15:30 IST session should verify completed bar!")
            self.assertEqual(len(cleaned_df), 2, "Both bars should be preserved after market close!")


if __name__ == "__main__":
    unittest.main()
