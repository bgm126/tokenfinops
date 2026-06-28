import logging
from sqlalchemy import select, func
from tokenfinops.models.usage import UsageRecord

logger = logging.getLogger(__name__)

class QualityPredictor:
    """Predicts whether an economy model will yield sufficient quality based on historical performance statistics."""

    async def predict_economy_success_probability(self, db_session, model_name: str) -> float:
        try:
            # Query success vs error ratios in past 100 calls
            stmt = select(
                func.count(UsageRecord.id).label("total"),
                func.sum(
                    case= {True: 1, False: 0}, 
                    value=(UsageRecord.status == "success")
                ).label("successes")
            ).where(
                UsageRecord.routed_model == model_name
            )
            
            # Wait, SQLAlchemy case/when mapping syntax varies. Let's do a direct SUM CASE syntax:
            # func.sum(case([(UsageRecord.status == "success", 1)], else_=0))
            # Or use func.count with filters, which works perfectly across all SQL engines:
            # func.count().filter(UsageRecord.status == "success")
            
            stmt = select(
                func.count(UsageRecord.id),
                func.count(UsageRecord.id).filter(UsageRecord.status == "success")
            ).where(UsageRecord.routed_model == model_name)
            
            result = await db_session.execute(stmt)
            total, successes = result.fetchone() or (0, 0)
            
            if total == 0:
                # Default prior probability if no data exists
                return 0.85
                
            prob = successes / total
            logger.debug(f"Quality predictor success probability for {model_name}: {prob:.2f} (based on {total} calls)")
            return prob
        except Exception as e:
            logger.warning(f"Failed to query quality statistics: {e}. Defaulting to standard prior.")
            return 0.85
