import logging
from datetime import datetime, timezone
from sqlalchemy import select
from tokenfinops.config import settings
from tokenfinops.engine.pipeline import PipelineStage, RequestContext
from tokenfinops.models.budget import Budget, BudgetUsage

logger = logging.getLogger(__name__)

class BudgetManager(PipelineStage):
    """Pipeline stage that enforces organizational budget policies, warning, and downgrading model tiers."""

    async def get_or_create_usage(self, session, budget: Budget) -> BudgetUsage:
        now = datetime.now(timezone.utc)
        # Determine start/end of current month
        start_time = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 12:
            end_time = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_time = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

        stmt = select(BudgetUsage).where(
            BudgetUsage.budget_id == budget.id,
            BudgetUsage.period_start == start_time
        )
        result = await session.execute(stmt)
        usage = result.scalar_one_or_none()

        if not usage:
            usage = BudgetUsage(
                budget_id=budget.id,
                period_start=start_time,
                period_end=end_time,
                spent=0.0,
                request_count=0
            )
            session.add(usage)
            await session.commit()
            await session.refresh(usage)
        
        return usage

    async def process(self, ctx: RequestContext) -> RequestContext:
        if not settings.ENABLE_BUDGET_ENFORCEMENT or not ctx.request.budget_id:
            return ctx

        # 1. Fetch budget config for team/id
        stmt = select(Budget).where(Budget.team_id == ctx.request.budget_id)
        result = await ctx.db_session.execute(stmt)
        budget = result.scalar_one_or_none()

        if not budget:
            return ctx

        # 2. Fetch current budget usage
        usage = await self.get_or_create_usage(ctx.db_session, budget)
        spent = float(usage.spent)
        limit_amount = float(budget.amount)

        # 3. Enforcement Checks
        # Check Hard Limit
        if spent >= limit_amount:
            ctx.aborted = True
            ctx.abort_reason = f"Hard budget limit of ${limit_amount:.2f} exceeded. Current spent: ${spent:.2f}."
            ctx.abort_status_code = 402  # Payment Required
            logger.warning(f"Budget exceeded for team '{budget.team_id}'. Request rejected.")
            return ctx

        # Check Soft Limit & Auto-Downgrade
        soft_limit_threshold = limit_amount * (float(budget.soft_limit_pct) / 100.0)
        if spent >= soft_limit_threshold:
            ctx.metadata["budget_status"] = "soft_limit_exceeded"
            logger.warning(f"Soft budget limit reached for team '{budget.team_id}'. spent: ${spent:.2f} / soft limit: ${soft_limit_threshold:.2f}.")
            
            # Perform automatic downgrade to cheaper model if configured
            if budget.downgrade_model:
                original_model = ctx.request.model
                ctx.request.model = budget.downgrade_model
                ctx.metadata["original_model_pre_budget_downgrade"] = original_model
                ctx.metadata["routing_reason"] = (
                    f"Soft budget limit exceeded. Auto-downgraded from {original_model} to {budget.downgrade_model}."
                )
                logger.info(f"Auto-downgraded requested model '{original_model}' -> '{budget.downgrade_model}' due to soft budget limit.")

        ctx.metadata["budget_spent"] = spent
        ctx.metadata["budget_limit"] = limit_amount
        return ctx

    @classmethod
    async def record_actual_spend(cls, db_session, budget_id: str, cost: float) -> None:
        """Update actual spends on completion of model calls."""
        if cost <= 0:
            return
        try:
            stmt = select(Budget).where(Budget.team_id == budget_id)
            result = await db_session.execute(stmt)
            budget = result.scalar_one_or_none()
            if not budget:
                return

            now = datetime.now(timezone.utc)
            start_time = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            
            stmt_usage = select(BudgetUsage).where(
                BudgetUsage.budget_id == budget.id,
                BudgetUsage.period_start == start_time
            )
            res_usage = await db_session.execute(stmt_usage)
            usage = res_usage.scalar_one_or_none()
            
            if usage:
                usage.spent = float(usage.spent) + cost
                usage.request_count += 1
                await db_session.commit()
        except Exception as e:
            logger.error(f"Failed to record actual spend for budget {budget_id}: {e}")
