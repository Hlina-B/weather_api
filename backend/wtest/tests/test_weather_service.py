"""The service decides cache vs. API and picks the current hour."""
from datetime import date

import pytest

from tests.helpers import FakeStrategy, hour_epoch, make_vc_response
from wapp.services import weather_service as service
from wapp.services.cache import redis_cache

# 2:00pm New York time on Nov 5 2026
NY_2PM = hour_epoch(2026, 11, 5, 14)


def test_cache_miss_fetches_from_provider_and_stores_result(fake_redis, use_strategy, now_is):
    strategy = use_strategy(FakeStrategy())
    now_is(NY_2PM)

    service.get_weather_data("10001", "us")

    assert strategy.calls == [{"zipcode": "10001", "unit_group": "us"}]
    assert redis_cache.get_agg_weather_data("10001", "us") is not None


def test_cache_hit_does_not_call_provider_again(fake_redis, use_strategy, now_is):
    strategy = use_strategy(FakeStrategy())
    now_is(NY_2PM)

    service.get_weather_data("10001", "us")
    service.get_weather_data("10001", "us")

    assert len(strategy.calls) == 1


def test_requested_unit_group_is_sent_to_provider(fake_redis, use_strategy, now_is):
    strategy = use_strategy(FakeStrategy())
    now_is(NY_2PM)

    service.get_weather_data("10001", "metric")

    assert strategy.calls[0]["unit_group"] == "metric"


def test_current_snapshot_is_the_current_hour(fake_redis, use_strategy, now_is):
    use_strategy(FakeStrategy())
    now_is(NY_2PM)

    result = service.get_weather_data("10001", "us")

    assert str(result.current_snapshot.date_time.date_time_epoch) == NY_2PM
    assert result.current_snapshot.date_time.date_time == "14:00:00"


@pytest.fixture
def la_now(fake_redis, use_strategy, now_is):
    use_strategy(FakeStrategy(make_vc_response(zipcode="90001", tz_name="America/Los_Angeles")))
    epoch = hour_epoch(2026, 11, 6, 1)  # 1:00am New York = 10:00pm Nov 5 Los Angeles
    now_is(epoch)
    return epoch


def test_current_hour_uses_the_locations_date(la_now):
    """At 1am Eastern on Nov 6 it is still 10pm Nov 5 in Los Angeles,
    so the snapshot must come from LA's Nov 5, not the server's date."""
    result = service.get_weather_data("90001", "us")

    assert str(result.current_snapshot.date_time.date_time_epoch) == la_now
    assert result.current_snapshot.date_time.date_time == "22:00:00"


def test_snapshot_is_not_written_into_the_cache(fake_redis, use_strategy, now_is):
    """A cached snapshot would freeze "current" weather until the TTL expires."""
    use_strategy(FakeStrategy())
    now_is(NY_2PM)

    service.get_weather_data("10001", "us")

    assert redis_cache.get_agg_weather_data("10001", "us").current_snapshot is None


def test_next_hour_gets_a_fresh_snapshot_from_the_cache(fake_redis, use_strategy, now_is):
    use_strategy(FakeStrategy())
    now_is(NY_2PM)
    service.get_weather_data("10001", "us")

    three_pm = hour_epoch(2026, 11, 5, 15)
    now_is(three_pm)
    result = service.get_weather_data("10001", "us")

    assert str(result.current_snapshot.date_time.date_time_epoch) == three_pm


def test_no_data_for_current_hour_raises(fake_redis, use_strategy, now_is):
    use_strategy(FakeStrategy(make_vc_response(start=date(2026, 12, 1))))
    now_is(NY_2PM)  # Nov 5: not in a forecast that starts Dec 1

    with pytest.raises(ValueError, match="No weather data found"):
        service.get_weather_data("10001", "us")


def test_clear_removes_cached_entry(fake_redis, use_strategy, now_is):
    use_strategy(FakeStrategy())
    now_is(NY_2PM)
    service.get_weather_data("10001", "us")

    service.clear_weather_data("10001", "us")

    assert redis_cache.get_agg_weather_data("10001", "us") is None
