from __future__ import annotations

from trading_agents.config import RiskConfig, settings
from trading_agents.core.blackboard import PipelineContext
from trading_agents.schemas import Order, OrderStatus, RiskAssessment, TradeAction


class RiskVetoGate:
    """
    Deterministic risk gate — LLM agents cannot override rejections.

    This is the safety boundary between AI reasoning and capital at risk.
    """

    agent_id = "risk_veto_gate"

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or settings.risk

    async def assess(self, ctx: PipelineContext) -> RiskAssessment:
        violations: list[str] = []
        proposal = ctx.proposal
        portfolio = ctx.portfolio

        if proposal is None:
            return RiskAssessment(approved=False, violations=["No trade proposal"])

        if proposal.action == TradeAction.HOLD:
            return RiskAssessment(approved=True, notes="Hold — no execution needed")

        if proposal.confidence < self.config.min_confidence:
            violations.append(
                f"Confidence {proposal.confidence:.2f} below minimum {self.config.min_confidence}"
            )

        if portfolio.orders_today >= self.config.max_orders_per_day:
            violations.append(f"Daily order limit reached ({self.config.max_orders_per_day})")

        price = proposal.limit_price or (ctx.snapshot.price if ctx.snapshot else 100.0)
        order_value = proposal.quantity * price
        portfolio_value = portfolio.cash + sum(
            abs(q) * price for q in portfolio.positions.values()
        ) or portfolio.cash

        position_pct = order_value / portfolio_value if portfolio_value > 0 else 1.0
        if position_pct > self.config.max_position_pct:
            violations.append(
                f"Position {position_pct:.1%} exceeds max {self.config.max_position_pct:.1%}"
            )

        if portfolio.daily_pnl < 0:
            daily_loss_pct = abs(portfolio.daily_pnl) / portfolio_value
            if daily_loss_pct >= self.config.max_daily_loss_pct:
                violations.append(
                    f"Daily loss circuit breaker: {daily_loss_pct:.1%} >= {self.config.max_daily_loss_pct:.1%}"
                )

        adjusted_quantity = proposal.quantity
        if violations and position_pct > self.config.max_position_pct:
            max_value = portfolio_value * self.config.max_position_pct
            adjusted_quantity = round(max_value / price, 2)
            if adjusted_quantity > 0 and len(violations) == 1:
                return RiskAssessment(
                    approved=True,
                    adjusted_quantity=adjusted_quantity,
                    notes=f"Quantity reduced from {proposal.quantity} to {adjusted_quantity}",
                )

        return RiskAssessment(
            approved=len(violations) == 0,
            violations=violations,
            adjusted_quantity=adjusted_quantity if not violations else None,
        )


class ExecutionAgent:
    agent_id = "execution_agent"

    async def execute(self, ctx: PipelineContext) -> Order:
        proposal = ctx.proposal
        if proposal is None:
            raise ValueError("No proposal to execute")

        quantity = proposal.quantity
        if ctx.risk and ctx.risk.adjusted_quantity is not None:
            quantity = ctx.risk.adjusted_quantity

        price = proposal.limit_price or (ctx.snapshot.price if ctx.snapshot else 100.0)
        # Paper mode: simulate immediate fill with small slippage
        slippage = 0.0005
        fill_price = price * (1 + slippage if proposal.action == TradeAction.BUY else 1 - slippage)

        order = Order(
            proposal_id=proposal.id,
            symbol=proposal.symbol,
            side=proposal.action,
            quantity=quantity,
            limit_price=proposal.limit_price,
            status=OrderStatus.FILLED,
            fill_price=round(fill_price, 4),
        )

        # Update portfolio state
        cost = quantity * fill_price
        if proposal.action == TradeAction.BUY:
            ctx.portfolio.cash -= cost
            ctx.portfolio.positions[proposal.symbol] = (
                ctx.portfolio.positions.get(proposal.symbol, 0) + quantity
            )
        elif proposal.action == TradeAction.SELL:
            ctx.portfolio.cash += cost
            ctx.portfolio.positions[proposal.symbol] = (
                ctx.portfolio.positions.get(proposal.symbol, 0) - quantity
            )
        ctx.portfolio.orders_today += 1

        return order
