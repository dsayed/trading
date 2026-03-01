"""Tests for CoveredCallAdvisor using hand-built fake option chains."""

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
from trading.plugins.advisors.covered_call import CoveredCallAdvisor


@pytest.fixture
def advisor():
    return CoveredCallAdvisor()


@pytest.fixture
def instrument():
    return Instrument(symbol="AAPL", asset_class=AssetClass.EQUITY)


def _make_option_chain(instrument: Instrument, current_price: float, dte: int = 30) -> OptionChain:
    """Build a realistic option chain for testing."""
    today = date.today()
    expiration = today + timedelta(days=dte)
    calls = [
        OptionContract(
            contract_symbol=f"AAPL{expiration.strftime('%y%m%d')}C{int(strike*1000):08d}",
            strike=strike,
            expiration=expiration,
            option_type="call",
            bid=max(0.1, (current_price - strike + 10) * 0.3) if strike > current_price else current_price - strike + 2.0,
            ask=max(0.2, (current_price - strike + 10) * 0.3 + 0.30) if strike > current_price else current_price - strike + 2.50,
            last_price=max(0.15, (current_price - strike + 10) * 0.3 + 0.15) if strike > current_price else current_price - strike + 2.25,
            volume=500 + int((current_price - strike + 20) * 50),
            open_interest=2000 + int((current_price - strike + 20) * 100),
            implied_volatility=0.30,
            in_the_money=strike < current_price,
        )
        for strike in [
            current_price - 10,
            current_price - 5,
            current_price + 5,
            current_price + 10,
            current_price + 15,
            current_price + 20,
        ]
    ]
    puts = [
        OptionContract(
            contract_symbol=f"AAPL{expiration.strftime('%y%m%d')}P{int(strike*1000):08d}",
            strike=strike,
            expiration=expiration,
            option_type="put",
            bid=1.0,
            ask=1.30,
            last_price=1.15,
            volume=200,
            open_interest=1000,
            implied_volatility=0.28,
            in_the_money=strike > current_price,
        )
        for strike in [current_price - 20, current_price - 10]
    ]
    return OptionChain(instrument=instrument, expiration=expiration, calls=calls, puts=puts)


class TestCoveredCallAdvisor:
    def test_satisfies_protocol(self, advisor):
        assert isinstance(advisor, PositionAdvisor)

    def test_name(self, advisor):
        assert advisor.name == "covered_call"

    def test_requires_100_shares(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=50, cost_basis=180.0, purchase_date=date(2025, 6, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 190.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 190.0)
        assert len(plays) == 0

    def test_generates_covered_call_with_100_shares(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 1, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 190.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 190.0)
        assert len(plays) == 1
        play = plays[0]
        assert play.play_type == PlayType.COVERED_CALL
        assert play.contracts == 1
        assert play.premium > 0

    def test_multiple_contracts_with_200_shares(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=200, cost_basis=180.0, purchase_date=date(2025, 1, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 190.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 190.0)
        assert len(plays) == 1
        assert plays[0].contracts == 2

    def test_selects_otm_call(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 1, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 190.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 190.0)
        assert len(plays) == 1
        assert plays[0].option_contract is not None
        assert plays[0].option_contract.strike > 190.0

    def test_tax_note_for_short_term_lots(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2026, 1, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 190.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 190.0)
        assert len(plays) == 1
        assert plays[0].tax_note is not None
        assert "short-term" in plays[0].tax_note

    def test_no_tax_note_for_long_term_lots(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2024, 1, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 190.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 190.0)
        assert len(plays) == 1
        assert plays[0].tax_note is None

    def test_playbook_has_sell_to_open(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 1, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 190.0)
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 190.0)
        assert "Sell to Open" in plays[0].playbook

    def test_no_plays_without_option_chains(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 1, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        plays = advisor.advise(pos, pd.DataFrame(), [], 190.0)
        assert len(plays) == 0

    def test_skips_chains_outside_dte_range(self, advisor, instrument):
        lot = TaxLot(instrument=instrument, quantity=100, cost_basis=180.0, purchase_date=date(2025, 1, 1))
        pos = Position(instrument=instrument, tax_lots=[lot])
        chain = _make_option_chain(instrument, 190.0, dte=90)  # Too far out
        plays = advisor.advise(pos, pd.DataFrame(), [chain], 190.0)
        assert len(plays) == 0
