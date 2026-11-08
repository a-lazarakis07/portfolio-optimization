import numpy as np
import pandas as pd
import pytest

from portfolio_backtester.data.history_audit import audit_universe_history


def sample():
    sessions = pd.bdate_range('2024-01-02', '2024-01-10', name='date')
    raw = pd.DataFrame({'date':sessions, 'ticker':'AAA', 'close':100., 'adjusted_close':100.,
                        'dividends':0., 'stock_splits':0.})
    returns = pd.DataFrame({'AAA':[np.nan, .01, .02, .03, .04, .05, .06]},index=sessions)
    universe = pd.DataFrame({'ticker':['AAA'],'company_name':['Sample Company'],'sector':['Industrials']})
    factors = pd.DataFrame({'mkt_rf':.01,'smb':.02,'hml':.01,'rmw':.01,'cma':.01,'mom':.01,'rf':.0001},index=sessions)
    policy = {'universe_version':'test','minimum_crisis_coverage':.95,'corporate_action_review_days':1,
              'adjustment_ratio_jump_threshold':.1,'crises':{'test':{'label':'Test event','start':'2024-01-08','end':'2024-01-10'}}}
    return raw,returns,universe,factors,policy,sessions


def test_coverage_and_pre_crisis_window_use_only_actual_past_returns():
    raw,returns,universe,factors,policy,sessions=sample()
    coverage,flags,events,summary=audit_universe_history(raw,returns,universe,factors,policy,window=3,minimum=2)
    row=coverage.iloc[0]
    assert row.data_coverage_percentage == 100
    assert row.test_pre_crisis_valid_observations == 3
    assert row.test_pre_crisis_estimation_eligible
    assert row.test_crisis_available
    assert flags.point_in_time_investability_verified.eq(False).all()
    assert summary['crises']['test']['available_tickers']==['AAA']


def test_missing_ipo_history_is_not_filled_or_counted_as_zero():
    raw,returns,universe,factors,policy,sessions=sample()
    raw=raw.loc[raw.date>=pd.Timestamp('2024-01-08')]
    returns.loc[:'2024-01-08','AAA']=np.nan
    coverage,flags,_,_=audit_universe_history(raw,returns,universe,factors,policy,window=3,minimum=2)
    assert coverage.iloc[0].test_pre_crisis_valid_observations == 0
    assert not coverage.iloc[0].test_pre_crisis_estimation_eligible
    assert flags.loc[flags.date<pd.Timestamp('2024-01-08'),'price_available'].eq(False).all()
    assert coverage.iloc[0].status == 'Limited'


def test_same_date_missing_factor_reduces_pre_crisis_observation_count():
    raw,returns,universe,factors,policy,_=sample()
    factors.loc['2024-01-04','mom']=np.nan
    coverage,_,_,_=audit_universe_history(raw,returns,universe,factors,policy,window=3,minimum=2)
    assert coverage.iloc[0].test_pre_crisis_valid_observations == 2


def test_predecessor_mapping_and_extreme_returns_remain_explicit_flags():
    raw,returns,universe,factors,policy,_=sample()
    returns.loc['2024-01-05','AAA']=.7
    profiles={'AAA':{'identity_valid_from':'2024-01-08','warning':'Mapped predecessor; review required','events':[{'date':'2024-01-08','type':'spin_off','description':'Test distribution'}]}}
    coverage,flags,events,_=audit_universe_history(raw,returns,universe,factors,policy,window=3,minimum=2,profiles=profiles)
    assert flags.loc[flags.date<pd.Timestamp('2024-01-08'),'predecessor_or_share_class_mapping'].all()
    assert flags.extreme_return_flag.sum()==1
    assert coverage.iloc[0].status=='Limited'
    assert not events.empty


def test_candidate_with_no_data_is_retained_as_ineligible():
    raw,returns,universe,factors,policy,_=sample()
    universe.loc[len(universe)]=['BBB','Unavailable Company','Industrials']
    coverage,flags,_,summary=audit_universe_history(raw,returns,universe,factors,policy,window=3,minimum=2)
    assert len(coverage)==2
    assert coverage.set_index('ticker').loc['BBB','status']=='Ineligible'
    assert not flags.loc[flags.ticker.eq('BBB'),'return_available'].any()


def test_legal_split_ratio_mismatch_is_flagged_without_rewriting_provider_prices():
    raw,returns,universe,factors,policy,_=sample()
    raw.loc[raw.date.eq('2024-01-08'),'stock_splits']=.9535
    before=raw.copy(deep=True)
    profiles={'AAA':{'warning':'Distribution and reverse split','events':[{'date':'2024-01-08','type':'spin_off_and_reverse_split','expected_stock_split':.5,'description':'Official reverse split'}]}}
    coverage,_,events,_=audit_universe_history(raw,returns,universe,factors,policy,window=3,minimum=2,profiles=profiles)
    assert coverage.iloc[0].corporate_action_field_mismatches==1
    assert 'provider_corporate_action_mismatch' in events.event_type.tolist()
    pd.testing.assert_frame_equal(raw,before)


def test_infinite_factor_is_not_a_valid_pre_crisis_observation():
    raw,returns,universe,factors,policy,_=sample()
    factors.loc['2024-01-04','mom']=np.inf
    coverage,_,_,_=audit_universe_history(raw,returns,universe,factors,policy,window=3,minimum=2)
    assert coverage.iloc[0].test_pre_crisis_valid_observations==2


def test_partial_audit_horizon_cannot_claim_full_crisis_coverage():
    raw,returns,universe,factors,policy,_=sample()
    coverage,_,_,_=audit_universe_history(raw,returns.loc['2024-01-09':],universe,factors,policy,window=3,minimum=2)
    assert not coverage.iloc[0].test_full_crisis_coverage
    assert coverage.iloc[0].test_crisis_return_coverage_percentage < 100


@pytest.mark.parametrize('profile', [
    {'warning': '', 'events': [{'date': '2024-01-08', 'type': 'spin_off',
                               'description': 'Distribution awaiting review'}]},
    {'warning': '', 'identity_valid_from': '2024-01-08'},
], ids=['corporate_action', 'ticker_mapping'])
def test_pending_review_without_warning_is_limited(profile):
    raw, returns, universe, factors, policy, _ = sample()
    coverage, flags, events, _ = audit_universe_history(
        raw, returns, universe, factors, policy, window=3, minimum=2,
        profiles={'AAA': profile})
    assert flags.predecessor_or_share_class_mapping.any() or events.review_required.any()
    assert coverage.iloc[0].corporate_action_ticker_history_warnings == ''
    assert coverage.iloc[0].status == 'Limited'


def test_invalid_ticker_is_excluded_from_pre_crisis_estimation_eligibility():
    raw, returns, universe, factors, policy, _ = sample()
    _, _, _, valid_summary = audit_universe_history(
        raw, returns, universe, factors, policy, window=3, minimum=2)
    assert valid_summary['crises']['test']['pre_crisis_estimation_eligible_tickers'] == ['AAA']
    coverage, _, _, summary = audit_universe_history(
        raw, returns, universe, factors, policy, window=3, minimum=2,
        invalid_tickers={'AAA'})
    assert coverage.iloc[0].status == 'Ineligible'
    assert coverage.iloc[0].test_pre_crisis_valid_observations == 3
    assert not coverage.iloc[0].test_pre_crisis_estimation_eligible
    assert summary['crises']['test']['pre_crisis_estimation_eligible_tickers'] == []


def test_invalid_ticker_is_excluded_from_identity_clear_pre_crisis_eligibility():
    raw, returns, universe, factors, policy, _ = sample()
    _, _, _, valid_summary = audit_universe_history(
        raw, returns, universe, factors, policy, window=3, minimum=2)
    assert valid_summary['crises']['test']['identity_clear_pre_crisis_eligible_tickers'] == ['AAA']
    coverage, _, _, summary = audit_universe_history(
        raw, returns, universe, factors, policy, window=3, minimum=2,
        invalid_tickers={'AAA'})
    assert coverage.iloc[0].status == 'Ineligible'
    assert coverage.iloc[0].test_identity_clear_pre_crisis_valid_observations == 3
    assert summary['crises']['test']['identity_clear_pre_crisis_eligible_tickers'] == []
