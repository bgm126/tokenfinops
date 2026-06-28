from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import select, func
from tokenfinops.models.usage import UsageRecord

logger = logging.getLogger(__name__)

class CostForecaster:
    """Predicts daily, weekly, and monthly AI spend trends based on historical call usage records."""

    async def forecast_monthly_spend(self, db_session, team_id: str | None = None) -> float:
        try:
            now = datetime.now(timezone.utc)
            thirty_days_ago = now - timedelta(days=30)
            
            # Query usage records in last 30 days
            stmt = select(
                func.sum(UsageRecord.actual_cost).label("total_spent"),
                func.count(UsageRecord.id).label("total_calls")
            ).where(
                UsageRecord.timestamp >= thirty_days_ago
            )
            
            if team_id:
                stmt = stmt.where(UsageRecord.team_id == team_id)

            result = await db_session.execute(stmt)
            row = result.fetchone()
            if not row or row[0] is None:
                return 0.0
                
            total_spent = float(row[0])
            total_calls = row[1]
            
            # Estimate monthly spend run rate (extrapolating if historical window is smaller)
            # Find earliest record in window
            stmt_min = select(func.min(UsageRecord.timestamp)).where(UsageRecord.timestamp >= thirty_days_ago)
            if team_id:
                stmt_min = stmt_min.where(UsageRecord.team_id == team_id)
            res_min = await db_session.execute(stmt_min)
            earliest_time = res_min.scalar()
            
            if not earliest_time:
                return total_spent

            days_active = (now - earliest_time).days + (now - earliest_time).seconds / 86400.0
            if days_active < 0.1:
                return total_spent
                
            daily_run_rate = total_spent / days_active
            forecast = daily_run_rate * 30.0
            logger.info(f"Forecasted 30-day spend: ${forecast:.2f} (Daily rate: ${daily_run_rate:.2f})")
            return forecast
        except Exception as e:
            logger.error(f"Failed to calculate cost forecast: {e}")
            return 0.0
