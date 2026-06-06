"""A simple long-only portfolio with cash, one position per symbol and costs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Position:
    symbol: str
    shares: float = 0.0
    avg_price: float = 0.0
    stop_price: float = 0.0
    target_price: float = 0.0


@dataclass
class Portfolio:
    """Tracks cash and positions and marks to market.

    Trades are expressed as *target weights* of total equity, which the
    portfolio converts into share deltas, charging a proportional commission.
    """

    cash: float = 100_000.0
    commission: float = 0.0005  # 5 bps per trade notional
    positions: dict[str, Position] = field(default_factory=dict)

    def position(self, symbol: str) -> Position:
        return self.positions.setdefault(symbol, Position(symbol=symbol))

    def market_value(self, prices: dict[str, float]) -> float:
        return sum(
            pos.shares * prices.get(sym, pos.avg_price) for sym, pos in self.positions.items()
        )

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + self.market_value(prices)

    def weight(self, symbol: str, prices: dict[str, float]) -> float:
        eq = self.equity(prices)
        if eq <= 0:
            return 0.0
        pos = self.positions.get(symbol)
        if not pos:
            return 0.0
        return (pos.shares * prices.get(symbol, pos.avg_price)) / eq

    def rebalance(
        self,
        symbol: str,
        target_weight: float,
        price: float,
        *,
        stop_loss_pct: float = 0.0,
        take_profit_pct: float = 0.0,
    ) -> None:
        """Move the position toward ``target_weight`` of current equity."""

        if price <= 0:
            return
        prices = {symbol: price}
        eq = self.equity(prices)
        target_value = max(0.0, target_weight) * eq
        target_shares = target_value / price

        pos = self.position(symbol)
        delta = target_shares - pos.shares
        if abs(delta * price) < 1e-6:
            return

        notional = abs(delta * price)
        fee = notional * self.commission

        if delta > 0:  # buy
            cost = delta * price + fee
            if cost > self.cash:  # scale down to available cash
                affordable = self.cash / (price * (1 + self.commission))
                delta = max(0.0, affordable)
                cost = delta * price + delta * price * self.commission
            total_shares = pos.shares + delta
            if total_shares > 0:
                pos.avg_price = (pos.avg_price * pos.shares + price * delta) / total_shares
            pos.shares = total_shares
            self.cash -= cost
        else:  # sell
            sell_shares = min(pos.shares, -delta)
            proceeds = sell_shares * price
            fee = proceeds * self.commission
            pos.shares -= sell_shares
            self.cash += proceeds - fee
            if pos.shares <= 1e-9:
                pos.shares = 0.0
                pos.avg_price = 0.0

        if pos.shares > 0:
            pos.stop_price = price * (1 - stop_loss_pct) if stop_loss_pct else 0.0
            pos.target_price = price * (1 + take_profit_pct) if take_profit_pct else 0.0

    def check_exits(self, prices: dict[str, float]) -> list[str]:
        """Liquidate positions whose stop-loss or take-profit triggered."""

        triggered: list[str] = []
        for sym, pos in self.positions.items():
            if pos.shares <= 0:
                continue
            price = prices.get(sym)
            if price is None:
                continue
            hit_stop = pos.stop_price and price <= pos.stop_price
            hit_target = pos.target_price and price >= pos.target_price
            if hit_stop or hit_target:
                proceeds = pos.shares * price
                self.cash += proceeds - proceeds * self.commission
                pos.shares = 0.0
                pos.avg_price = 0.0
                pos.stop_price = 0.0
                pos.target_price = 0.0
                triggered.append(sym)
        return triggered
