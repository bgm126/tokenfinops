import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from tokenfinops.models.usage import UsageRecord

logger = logging.getLogger(__name__)

class AnomalyDetector:
    """Monitors request cost spikes and usage patterns to identify spikes or abuse anomalies."""

    async def detect_cost_anomaly(self, db_session, window_hours: int = 24) -> tuple[bool, str]:
        """Check if spend in the last window_hours deviates significantly from historical patterns."""
        try:
            now = datetime.now(timezone.utc)
            start_check = now - timedelta(hours=window_hours)
            
            # 1. Query current window spend
            stmt_curr = select(func.sum(UsageRecord.actual_cost)).where(
                UsageRecord.timestamp >= start_check
            )
            res_curr = await db_session.execute(stmt_curr)
            curr_spent = float(res_curr.scalar() or 0.0)
            
            # 2. Query historical daily spends for the past 14 days
            hist_start = now - timedelta(days=14)
            stmt_hist = select(
                func.date_trunc('day', UsageRecord.timestamp).label('day'),
                func.sum(UsageRecord.actual_cost).label('spent')
            ).where(
                UsageRecord.timestamp >= hist_start,
                UsageRecord.timestamp < start_check
            ).group_by('day')
            
            res_hist = await db_session.execute(stmt_hist)
            daily_spends = [float(row[1]) for row in res_hist.fetchall() if row[1] is not None]
            
            if len(daily_spends) < 3:
                # Not enough historical baseline data yet
                return False, "Insufficient baseline data."

            # Calculate mean and standard deviation
            mean_spent = sum(daily_spends) / len(daily_spends)
            variance = sum((x - mean_spent) ** 2 for x in daily_spends) / len(daily_spends)
            std_dev = variance ** 0.5
            
            # Scale historical mean down to matching hour window size for direct comparison
            scale_factor = window_hours / 24.0
            expected_mean = mean_spent * scale_factor
            expected_std_dev = std_dev * scale_factor
            
            # Threshold: 3 Standard Deviations above mean
            threshold = expected_mean + max(3.0 * expected_std_dev, 1.0)  # Min $1 std dev check
            
            if curr_spent > threshold:
                msg = f"Cost spike detected! Spent ${curr_spent:.2f} in last {window_hours} hours, exceeding threshold of ${threshold:.2f} (mean: ${expected_mean:.2f})."
                logger.warning(msg)
                return True, msg
                
            return False, "Normal spend patterns."
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return False, str(e)
