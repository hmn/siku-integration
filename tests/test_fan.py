"""Tests for SikuFan entity."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.siku.fan import SikuFan
from custom_components.siku.const import (
    DIRECTIONS,
    DIRECTION_ALTERNATING,
    DIRECTION_FORWARD,
    FAN_SPEEDS,
    PRESET_MODE_AUTO,
    PRESET_MODE_MANUAL,
    PRESET_MODE_ON,
    PRESET_MODE_PARTY,
    PRESET_MODE_SLEEP,
)

# ruff: noqa: D103


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator_data(
    *,
    is_on: bool = True,
    speed: str = "01",
    manual_speed_selected: bool = False,
    manual_speed: int = 50,
    manual_speed_low_high_range: tuple = (1, 100),
    speed_list: list | None = None,
    oscillating: bool = False,
    direction: str | None = DIRECTIONS[DIRECTION_FORWARD],
):
    return {
        "is_on": is_on,
        "speed": speed,
        "manual_speed_selected": manual_speed_selected,
        "manual_speed": manual_speed,
        "manual_speed_low_high_range": manual_speed_low_high_range,
        "speed_list": speed_list,
        "oscillating": oscillating,
        "direction": direction,
    }


def _make_fan(coordinator_data: dict | None = None) -> SikuFan:
    """Return a SikuFan with mocked hass and coordinator."""
    hass = MagicMock()

    # Make async_add_executor_job actually call the function synchronously so
    # we don't have to await nothing in unit tests.
    async def _add_executor_job(fn, *args):
        return fn(*args)

    hass.async_add_executor_job = _add_executor_job

    coordinator = MagicMock()
    coordinator.data = coordinator_data or _make_coordinator_data()
    coordinator.api = MagicMock()
    coordinator.api.power_off = AsyncMock()
    coordinator.api.power_on = AsyncMock()
    coordinator.api.speed = AsyncMock()
    coordinator.api.speed_manual = AsyncMock()
    coordinator.api.party = AsyncMock()
    coordinator.api.sleep = AsyncMock()
    coordinator.api.direction = AsyncMock()
    coordinator.api.host = "192.168.1.1"
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test_entry"

    fan = SikuFan.__new__(SikuFan)
    fan.hass = hass
    fan.coordinator = coordinator
    fan._attr_name = "Siku Fan"
    fan._attr_unique_id = "siku-test-fan"
    fan._attr_device_info = {}
    fan._attr_preset_mode = PRESET_MODE_ON
    fan._attr_percentage = 33
    fan._attr_oscillating = False
    fan._attr_current_direction = DIRECTIONS[DIRECTION_FORWARD]
    return fan


# ---------------------------------------------------------------------------
# Bug #147 – preset_mode must never become None
# ---------------------------------------------------------------------------


class TestPresetModeNeverNone:
    """Regression tests for issue #147.

    When the fan is turned off the preset_mode must remain a valid value
    (one of: auto, manual, on, party, sleep).  Setting it to None causes HA
    to raise "The default is invalid. Valid defaults are: auto, manual, on,
    party, sleep."
    """

    # --- set_percentage(0) --------------------------------------------------

    def test_set_percentage_zero_does_not_set_preset_to_none(self):
        """set_percentage(0) must NOT set preset_mode to None (bug #147)."""
        fan = _make_fan()
        fan._attr_preset_mode = PRESET_MODE_ON

        fan.set_percentage(0)

        assert fan._attr_preset_mode is not None, (
            "preset_mode became None after set_percentage(0) – this is the bug "
            "reported in issue #147"
        )

    def test_set_percentage_zero_keeps_previous_preset_mode(self):
        """set_percentage(0) must preserve the current preset_mode value."""
        for preset in [
            PRESET_MODE_ON,
            PRESET_MODE_AUTO,
            PRESET_MODE_MANUAL,
            PRESET_MODE_PARTY,
            PRESET_MODE_SLEEP,
        ]:
            fan = _make_fan()
            fan._attr_preset_mode = preset
            fan.set_percentage(0)
            assert fan._attr_preset_mode == preset, (
                f"preset_mode changed from {preset!r} to {fan._attr_preset_mode!r} "
                f"after set_percentage(0)"
            )

    def test_set_percentage_zero_preset_is_in_valid_modes(self):
        """After set_percentage(0) preset_mode must still be in _attr_preset_modes."""
        fan = _make_fan()
        fan._attr_preset_mode = PRESET_MODE_ON
        fan.set_percentage(0)
        assert fan._attr_preset_mode in fan._attr_preset_modes, (
            f"preset_mode {fan._attr_preset_mode!r} is not in "
            f"the list of valid preset modes after set_percentage(0)"
        )

    # --- async_set_percentage(0) --------------------------------------------

    @pytest.mark.asyncio
    async def test_async_set_percentage_zero_does_not_set_preset_to_none(self):
        """async_set_percentage(0) must NOT leave preset_mode as None."""
        fan = _make_fan()
        fan._attr_preset_mode = PRESET_MODE_ON
        fan.async_write_ha_state = MagicMock()
        fan.schedule_update_ha_state = MagicMock()

        await fan.async_set_percentage(0)

        assert fan._attr_preset_mode is not None, (
            "preset_mode became None after async_set_percentage(0) – bug #147"
        )

    @pytest.mark.asyncio
    async def test_async_set_percentage_zero_preset_is_valid(self):
        """After async_set_percentage(0) preset_mode must be in the valid list."""
        fan = _make_fan()
        fan._attr_preset_mode = PRESET_MODE_AUTO
        fan.async_write_ha_state = MagicMock()
        fan.schedule_update_ha_state = MagicMock()

        await fan.async_set_percentage(0)

        assert fan._attr_preset_mode in fan._attr_preset_modes, (
            f"preset_mode {fan._attr_preset_mode!r} is not valid after turn-off"
        )

    # --- async_turn_off -------------------------------------------------------

    @pytest.mark.asyncio
    async def test_turn_off_does_not_set_preset_to_none(self):
        """async_turn_off() must NOT leave preset_mode as None (bug #147)."""
        fan = _make_fan()
        fan._attr_preset_mode = PRESET_MODE_ON
        fan.async_write_ha_state = MagicMock()
        fan.schedule_update_ha_state = MagicMock()

        await fan.async_turn_off()

        assert fan._attr_preset_mode is not None, (
            "preset_mode became None after async_turn_off() – bug #147"
        )

    @pytest.mark.asyncio
    async def test_turn_off_preset_is_in_valid_modes(self):
        """After async_turn_off() preset_mode must remain in _attr_preset_modes."""
        fan = _make_fan()
        fan._attr_preset_mode = PRESET_MODE_ON
        fan.async_write_ha_state = MagicMock()
        fan.schedule_update_ha_state = MagicMock()

        await fan.async_turn_off()

        assert fan._attr_preset_mode in fan._attr_preset_modes

    # --- _handle_coordinator_update with is_on=False --------------------------

    def test_coordinator_update_fan_off_preset_not_none(self):
        """When coordinator reports is_on=False preset_mode must stay valid."""
        data = _make_coordinator_data(is_on=False)
        fan = _make_fan(coordinator_data=data)
        fan._attr_preset_mode = PRESET_MODE_ON
        fan.schedule_update_ha_state = MagicMock()
        fan.async_write_ha_state = MagicMock()

        # Simulate a coordinator update with the fan off
        fan.coordinator.data = data
        fan._handle_coordinator_update()

        assert fan._attr_preset_mode is not None, (
            "preset_mode became None after _handle_coordinator_update with "
            "is_on=False – bug #147"
        )

    def test_coordinator_update_fan_off_preset_is_valid(self):
        """When coordinator reports is_on=False preset_mode must be in valid list."""
        data = _make_coordinator_data(is_on=False)
        fan = _make_fan(coordinator_data=data)
        fan._attr_preset_mode = PRESET_MODE_AUTO
        fan.schedule_update_ha_state = MagicMock()
        fan.async_write_ha_state = MagicMock()

        fan.coordinator.data = data
        fan._handle_coordinator_update()

        assert fan._attr_preset_mode in fan._attr_preset_modes, (
            f"preset_mode {fan._attr_preset_mode!r} is not valid after "
            f"coordinator update with is_on=False"
        )

    def test_coordinator_update_fan_off_keeps_previous_preset(self):
        """When coordinator says fan is off the previous preset_mode is preserved."""
        data = _make_coordinator_data(is_on=False)
        fan = _make_fan(coordinator_data=data)
        fan.schedule_update_ha_state = MagicMock()
        fan.async_write_ha_state = MagicMock()

        for preset in [
            PRESET_MODE_ON,
            PRESET_MODE_AUTO,
            PRESET_MODE_MANUAL,
            PRESET_MODE_PARTY,
            PRESET_MODE_SLEEP,
        ]:
            fan._attr_preset_mode = preset
            fan.coordinator.data = data
            fan._handle_coordinator_update()
            assert fan._attr_preset_mode == preset, (
                f"preset_mode changed from {preset!r} to "
                f"{fan._attr_preset_mode!r} when fan turned off"
            )

    # --- async_set_percentage(0) with manual_speed_selected -------------------

    @pytest.mark.asyncio
    async def test_async_set_percentage_zero_manual_selected_preset_not_none(self):
        """async_set_percentage(0) with manual_speed_selected must not set None."""
        data = _make_coordinator_data(
            is_on=True,
            manual_speed_selected=True,
            manual_speed=50,
        )
        fan = _make_fan(coordinator_data=data)
        # When manual_speed_selected and preset is NOT manual, old code set None
        fan._attr_preset_mode = PRESET_MODE_ON
        fan.async_write_ha_state = MagicMock()
        fan.schedule_update_ha_state = MagicMock()

        await fan.async_set_percentage(0)

        assert fan._attr_preset_mode is not None, (
            "preset_mode became None during turn-off with manual_speed_selected=True"
        )


# ---------------------------------------------------------------------------
# Bug: is_on incorrectly True when fan is off but preset_mode is preserved
# ---------------------------------------------------------------------------


class TestIsOnWhenFanOff:
    """When the fan is physically off (percentage=0) is_on must return False.

    HA's default FanEntity.is_on formula:
        (percentage > 0) OR (preset_mode is not None)
    causes is_on=True whenever a preset is retained after turn-off (#147 fix).
    SikuFan must override is_on to use only the percentage.
    """

    def test_is_on_false_when_percentage_zero_preset_on(self):
        """is_on must be False when percentage=0, even if preset_mode=PRESET_MODE_ON."""
        fan = _make_fan()
        fan._attr_percentage = 0
        fan._attr_preset_mode = PRESET_MODE_ON

        assert fan.is_on is False, (
            "is_on returned True for a fan that is off (percentage=0) but has "
            "preset_mode=PRESET_MODE_ON preserved. HA's default formula treats "
            "non-None preset_mode as 'on', hiding the fact the fan is physically off."
        )

    def test_is_on_false_when_percentage_zero_preset_auto(self):
        """is_on must be False when percentage=0 regardless of preset_mode value."""
        for preset in [
            PRESET_MODE_ON,
            PRESET_MODE_AUTO,
            PRESET_MODE_MANUAL,
            PRESET_MODE_PARTY,
            PRESET_MODE_SLEEP,
        ]:
            fan = _make_fan()
            fan._attr_percentage = 0
            fan._attr_preset_mode = preset
            assert fan.is_on is False, (
                f"is_on returned True when percentage=0 and preset_mode={preset!r}"
            )

    def test_is_on_true_when_percentage_nonzero(self):
        """is_on must be True when percentage > 0."""
        fan = _make_fan()
        fan._attr_percentage = 33
        fan._attr_preset_mode = PRESET_MODE_ON
        assert fan.is_on is True

    def test_is_on_none_when_percentage_is_none(self):
        """is_on must be None/falsy when percentage is None."""
        fan = _make_fan()
        fan._attr_percentage = None
        fan._attr_preset_mode = None
        # Should not be True – fan has no known state
        assert not fan.is_on


# ---------------------------------------------------------------------------
# Reapply same preset when fan is off (requires is_on to be correct first)
# ---------------------------------------------------------------------------


class TestReapplySamePresetWhenFanOff:
    """Setting a preset_mode equal to the current one must still turn the fan on.

    After the #147 fix the entity retains its preset_mode when turned off.
    If is_on is also correctly False, HA will call async_set_preset_mode when
    the user selects any preset (including the preserved one).  The method must
    power on the fan regardless of whether the preset value changed.
    """

    @pytest.mark.asyncio
    async def test_set_same_preset_when_off_calls_power_on(self):
        """async_set_preset_mode with the same preset while off must call power_on."""
        data = _make_coordinator_data(is_on=False)
        fan = _make_fan(coordinator_data=data)
        fan._attr_percentage = 0
        fan._attr_preset_mode = PRESET_MODE_ON  # preserved from before turn-off
        fan.async_write_ha_state = MagicMock()
        fan.schedule_update_ha_state = MagicMock()

        await fan.async_set_preset_mode(PRESET_MODE_ON)

        fan.coordinator.api.power_on.assert_called()

    @pytest.mark.asyncio
    async def test_set_same_preset_auto_when_off_calls_power_on(self):
        """async_set_preset_mode(auto) while off must call power_on even if already auto."""
        data = _make_coordinator_data(is_on=False)
        fan = _make_fan(coordinator_data=data)
        fan._attr_percentage = 0
        fan._attr_preset_mode = PRESET_MODE_AUTO
        fan.async_write_ha_state = MagicMock()
        fan.schedule_update_ha_state = MagicMock()

        await fan.async_set_preset_mode(PRESET_MODE_AUTO)

        fan.coordinator.api.power_on.assert_called()

    @pytest.mark.asyncio
    async def test_set_same_preset_manual_when_off_calls_power_on(self):
        """async_set_preset_mode(manual) while off must call power_on even if already manual."""
        data = _make_coordinator_data(is_on=False)
        fan = _make_fan(coordinator_data=data)
        fan._attr_percentage = 0
        fan._attr_preset_mode = PRESET_MODE_MANUAL
        fan.async_write_ha_state = MagicMock()
        fan.schedule_update_ha_state = MagicMock()

        await fan.async_set_preset_mode(PRESET_MODE_MANUAL)

        fan.coordinator.api.power_on.assert_called()
