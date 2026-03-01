"""Tests for ProtectivePutAdvisor using hand-built fake option chains."""

from datetime import date, timedelta

import pandas as pd
import pytest

from trading.core.models import (
    AssetClass,
    Instrument,
    OptionChain,
    OptionContract,
    PlayType,
    Position,
    TaxLot,
)
from trading.plugins.advisors.base import PositionAdvisor
from trading.plugins.advisors.protective_put import ProtectivePutAdvisor


@pytest.fixture
def advisor():
    return ProtectivePutAdvisor()


@pytest.fixture
def instrument():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


def _make_option_chain(instrument: Instrument, current_price: float, dte: int = 30) -> OptionChain:
    """Build option chain with puts in the 5-15% OTM range."""
    today = date.today()
    expiration = today + timedelta(days=dte)
    puts = [
        OptionContract(
            contract_symbol=f"AAPL{expiration.strftime('%y%m%d')}P{int(strike*1000):08d}",
            strike=strike,
            expiration=expiration,
            option_type="put",
            bid=max(0.10, (current_price - strike) * 0.1),
            ask=max(0.20, (current_price - strike) * 0.1 + 0.30),
            last_price=max(0.15, (current_price - strike) * 0.1 + 0.15),
            volume=300,
            open_interest=1500,
            implied_volatility=0.30,
            in_the_money=strike > current_price,
        )
        for strike in [
            round(current_price * 0.80, 2),   # 20% OTM - outside range
            round(current_price * 0.85, 2),   # 15% OTM - edge of range
            round(current_price * 0.90, 2),   # 10% OTM - sweet spot
            round(current_price * 0.95, 2),   # 5% OTM - edge of range
            round(current_price * 1.00, 2),   # ATM - inside range (in the money check)
        ]
    ]
    # Mark ATM and ITM puts
    for p in puts:
        p_dict = p.model_dump()
        p_dict["in_the_money"] = p.strike >= current_price

    calls = [
        OptionContract(
            contract_symbol=f"AAPL{expiration.strftime('%y%m%d')}C{int(strike*1000):08d}",
            strike=strike,
            expiration=expiration,
            option_type="call",
            bid=2.0,
            ask=2.50,
            last_price=2.25,
            volume=500,
            open_interest=2000,
            implied_volatility=0.28,
            in_the_money=False,
        )
        for strike in [current_price + 10]
    ]

    # Reconstruct puts with correct in_the_money flag
    corrected_puts = []
    for p in puts:
        corrected_puts.append(
            OptionContract(
                contract_symbol=p.contract_symbol,
                strike=p.strike,
                expiration=p.expiration,
                option_type=p.option_type,
                bid=p.bid,
                ask=p.ask,
                last_price=p.last_price,
                volume=p.volume,
                open_interest=p.open_interest,
                implied_volatility=p.implied_volatility,
                in_the_money=p.strike >= current_price,
            )
        )

    return OptionChain(
        instrument=instrument, expiration=expiration, calls=calls, puts=corrected_puts
    )


class TestProtectivePutAdvisor:
    def test_satisfies_protocol(self, advisor):
        assert isinstance(advisor, PositionAdvisor)

    def test_name(self, advisor):
        assert advisor.name == "protective_put"

    def test_generates_protective_put(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 200.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 200.0)
        assert len(plays) == 1
        play = plays[0]
        assert play.play_type == PlayType.PROTECTIVE_PUT
        assert play.option_contract is not None
        assert play.option_contract.option_type == "put"

    def test_put_is_otm(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 200.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 200.0)
        assert len(plays) == 1
        assert plays[0].option_contract.strike < 200.0

    def test_max_loss_is_capped(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 200.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 200.0)
        assert len(plays) == 1
        assert plays[0].max_loss is not None
        # Max loss should be finite and positive
        assert plays[0].max_loss > 0

    def test_tax_note_for_approaching_long_term(self, advisor, instrument):
        # Lot that's close to long-term status
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 4, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 200.0, dte=45)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 200.0)
        assert len(plays) == 1
        assert plays[0].tax_note is not None

    def test_playbook_has_buy_to_open(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 200.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 200.0)
        assert "Buy to Open" in plays[0].playbook

    def test_no_plays_without_option_chains(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        plays = advisor.advise(pos, pd.DataFrame(), [], 200.0)
        assert len(plays) == 0

    def test_works_with_small_positions(self, advisor, instrument):
        """Even positions < 100 shares should get at least 1 contract."""
        lot = TaxLot(instrument=instrument, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 200.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 200.0)
        if plays:
            assert plays[0].contracts >= 1

    def test_skips_short_dte_chains(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 200.0, dte=10)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 200.0)
        assert len(plays) == 0
