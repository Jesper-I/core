"""Tests for gree component."""
from datetime import timedelta
from unittest.mock import DEFAULT as DEFAULT_MOCK, AsyncMock, patch

from greeclimate.device import HorizontalSwing, VerticalSwing
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.gree.climate import FAN_MODES_REVERSE, HVAC_MODES_REVERSE
from homeassistant.components.gree.const import FAN_MEDIUM_HIGH, FAN_MEDIUM_LOW
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .common import async_setup_gree, build_device_mock

from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake_device_1"


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def test_discovery_called_once(hass: HomeAssistant, discovery, device) -> None:
    """Test discovery is only ever called once."""
    await async_setup_gree(hass)
    assert discovery.call_count == 1

    await async_setup_gree(hass)
    assert discovery.call_count == 1


async def test_discovery_setup(hass: HomeAssistant, discovery, device) -> None:
    """Test setup of platform."""
    MockDevice1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
    )
    MockDevice2 = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.2", mac="bbccdd223344"
    )

    discovery.return_value.mock_devices = [MockDevice1, MockDevice2]
    device.side_effect = [MockDevice1, MockDevice2]

    await async_setup_gree(hass)
    await hass.async_block_till_done()
    assert discovery.call_count == 1
    assert len(hass.states.async_all(DOMAIN)) == 2


async def test_discovery_setup_connection_error(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Test gree integration is setup."""
    MockDevice1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
    )
    MockDevice1.bind = AsyncMock(side_effect=DeviceNotBoundError)
    MockDevice1.update_state = AsyncMock(side_effect=DeviceNotBoundError)

    discovery.return_value.mock_devices = [MockDevice1]
    device.return_value = MockDevice1

    await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(DOMAIN)) == 1
    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state == STATE_UNAVAILABLE


async def test_discovery_after_setup(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Test gree devices don't change after multiple discoveries."""
    MockDevice1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
    )
    MockDevice1.bind = AsyncMock(side_effect=DeviceNotBoundError)

    MockDevice2 = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.2", mac="bbccdd223344"
    )
    MockDevice2.bind = AsyncMock(side_effect=DeviceTimeoutError)

    discovery.return_value.mock_devices = [MockDevice1, MockDevice2]
    device.side_effect = [MockDevice1, MockDevice2]

    await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 1
    assert len(hass.states.async_all(DOMAIN)) == 2

    # rediscover the same devices shouldn't change anything
    discovery.return_value.mock_devices = [MockDevice1, MockDevice2]
    device.side_effect = [MockDevice1, MockDevice2]

    next_update = mock_now + timedelta(minutes=6)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 2
    assert len(hass.states.async_all(DOMAIN)) == 2


async def test_discovery_add_device_after_setup(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Test gree devices can be added after initial setup."""
    MockDevice1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
    )
    MockDevice1.bind = AsyncMock(side_effect=DeviceNotBoundError)

    MockDevice2 = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.2", mac="bbccdd223344"
    )
    MockDevice2.bind = AsyncMock(side_effect=DeviceTimeoutError)

    discovery.return_value.mock_devices = [MockDevice1]
    device.side_effect = [MockDevice1]

    await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 1
    assert len(hass.states.async_all(DOMAIN)) == 1

    # rediscover the same devices shouldn't change anything
    discovery.return_value.mock_devices = [MockDevice2]
    device.side_effect = [MockDevice2]

    next_update = mock_now + timedelta(minutes=6)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert discovery.return_value.scan_count == 2
    assert len(hass.states.async_all(DOMAIN)) == 2


async def test_discovery_device_bind_after_setup(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Test gree devices can be added after a late device bind."""
    MockDevice1 = build_device_mock(
        name="fake-device-1", ipAddress="1.1.1.1", mac="aabbcc112233"
    )
    MockDevice1.bind = AsyncMock(side_effect=DeviceNotBoundError)
    MockDevice1.update_state = AsyncMock(side_effect=DeviceNotBoundError)

    discovery.return_value.mock_devices = [MockDevice1]
    device.return_value = MockDevice1

    await async_setup_gree(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(DOMAIN)) == 1
    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state == STATE_UNAVAILABLE

    # Now the device becomes available
    MockDevice1.bind.side_effect = None
    MockDevice1.update_state.side_effect = None

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE


async def test_update_connection_failure(hass: HomeAssistant, device, mock_now) -> None:
    """Testing update hvac connection failure exception."""
    device().update_state.side_effect = [
        DEFAULT_MOCK,
        DeviceTimeoutError,
        DeviceTimeoutError,
    ]

    await async_setup_gree(hass)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    # First update to make the device available
    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state != STATE_UNAVAILABLE

    next_update = mock_now + timedelta(minutes=10)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    next_update = mock_now + timedelta(minutes=15)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    # Then two more update failures to make the device unavailable
    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state == STATE_UNAVAILABLE


async def test_update_connection_failure_recovery(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Testing update hvac connection failure recovery."""
    device().update_state.side_effect = [
        DeviceTimeoutError,
        DeviceTimeoutError,
        DEFAULT_MOCK,
    ]

    await async_setup_gree(hass)

    # First update becomes unavailable
    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state == STATE_UNAVAILABLE

    # Second update restores the connection
    next_update = mock_now + timedelta(minutes=10)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state != STATE_UNAVAILABLE


async def test_update_unhandled_exception(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Testing update hvac connection unhandled response exception."""
    device().update_state.side_effect = [DEFAULT_MOCK, Exception]

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state != STATE_UNAVAILABLE

    next_update = mock_now + timedelta(minutes=10)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state == STATE_UNAVAILABLE


async def test_send_command_device_timeout(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Test for sending power on command to the device with a device timeout."""
    await async_setup_gree(hass)

    # First update to make the device available
    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state != STATE_UNAVAILABLE

    device().push_state_update.side_effect = DeviceTimeoutError

    # Send failure should not raise exceptions or change device state
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_send_power_on(hass: HomeAssistant, discovery, device, mock_now) -> None:
    """Test for sending power on command to the device."""
    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_send_power_off_device_timeout(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Test for sending power off command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.parametrize(
    "units,temperature",
    [(UnitOfTemperature.CELSIUS, 26), (UnitOfTemperature.FAHRENHEIT, 74)],
)
async def test_send_target_temperature(
    hass: HomeAssistant, discovery, device, units, temperature
) -> None:
    """Test for sending target temperature command to the device."""
    hass.config.units.temperature_unit = units

    fake_device = device()
    if units == UnitOfTemperature.FAHRENHEIT:
        fake_device.temperature_units = 1

    await async_setup_gree(hass)

    # Make sure we're trying to test something that isn't the default
    assert fake_device.current_temperature != temperature

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: temperature},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature
    assert (
        state.attributes.get(ATTR_CURRENT_TEMPERATURE)
        == fake_device.current_temperature
    )

    # Reset config temperature_unit back to CELSIUS, required for
    # additional tests outside this component.
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS


@pytest.mark.parametrize(
    "units,temperature",
    [(UnitOfTemperature.CELSIUS, 25), (UnitOfTemperature.FAHRENHEIT, 74)],
)
async def test_send_target_temperature_device_timeout(
    hass: HomeAssistant, discovery, device, units, temperature
) -> None:
    """Test for sending target temperature command to the device with a device timeout."""
    hass.config.units.temperature_unit = units
    if units == UnitOfTemperature.FAHRENHEIT:
        device().temperature_units = 1
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: temperature},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature

    # Reset config temperature_unit back to CELSIUS, required for additional tests outside this component.
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS


@pytest.mark.parametrize(
    "units,temperature",
    [(UnitOfTemperature.CELSIUS, 25), (UnitOfTemperature.FAHRENHEIT, 74)],
)
async def test_update_target_temperature(
    hass: HomeAssistant, discovery, device, units, temperature
) -> None:
    """Test for updating target temperature from the device."""
    hass.config.units.temperature_unit = units
    if units == UnitOfTemperature.FAHRENHEIT:
        device().temperature_units = 1
    device().target_temperature = temperature

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature

    # Reset config temperature_unit back to CELSIUS, required for additional tests outside this component.
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS


@pytest.mark.parametrize(
    "preset", (PRESET_AWAY, PRESET_ECO, PRESET_SLEEP, PRESET_BOOST, PRESET_NONE)
)
async def test_send_preset_mode(
    hass: HomeAssistant, discovery, device, mock_now, preset
) -> None:
    """Test for sending preset mode command to the device."""
    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == preset


async def test_send_invalid_preset_mode(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Test for sending preset mode command to the device."""
    await async_setup_gree(hass)

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: "invalid"},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) != "invalid"


@pytest.mark.parametrize(
    "preset", (PRESET_AWAY, PRESET_ECO, PRESET_SLEEP, PRESET_BOOST, PRESET_NONE)
)
async def test_send_preset_mode_device_timeout(
    hass: HomeAssistant, discovery, device, mock_now, preset
) -> None:
    """Test for sending preset mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == preset


@pytest.mark.parametrize(
    "preset", (PRESET_AWAY, PRESET_ECO, PRESET_SLEEP, PRESET_BOOST, PRESET_NONE)
)
async def test_update_preset_mode(
    hass: HomeAssistant, discovery, device, mock_now, preset
) -> None:
    """Test for updating preset mode from the device."""
    device().steady_heat = preset == PRESET_AWAY
    device().power_save = preset == PRESET_ECO
    device().sleep = preset == PRESET_SLEEP
    device().turbo = preset == PRESET_BOOST

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == preset


@pytest.mark.parametrize(
    "hvac_mode",
    (
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT,
    ),
)
async def test_send_hvac_mode(
    hass: HomeAssistant, discovery, device, mock_now, hvac_mode
) -> None:
    """Test for sending hvac mode command to the device."""
    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    "hvac_mode",
    (HVACMode.AUTO, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.HEAT),
)
async def test_send_hvac_mode_device_timeout(
    hass: HomeAssistant, discovery, device, mock_now, hvac_mode
) -> None:
    """Test for sending hvac mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    "hvac_mode",
    (
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT,
    ),
)
async def test_update_hvac_mode(
    hass: HomeAssistant, discovery, device, mock_now, hvac_mode
) -> None:
    """Test for updating hvac mode from the device."""
    device().power = hvac_mode != HVACMode.OFF
    device().mode = HVAC_MODES_REVERSE.get(hvac_mode)

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    "fan_mode",
    (FAN_AUTO, FAN_LOW, FAN_MEDIUM_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH),
)
async def test_send_fan_mode(
    hass: HomeAssistant, discovery, device, mock_now, fan_mode
) -> None:
    """Test for sending fan mode command to the device."""
    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


async def test_send_invalid_fan_mode(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Test for sending fan mode command to the device."""
    await async_setup_gree(hass)

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "invalid"},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) != "invalid"


@pytest.mark.parametrize(
    "fan_mode",
    (FAN_AUTO, FAN_LOW, FAN_MEDIUM_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH),
)
async def test_send_fan_mode_device_timeout(
    hass: HomeAssistant, discovery, device, mock_now, fan_mode
) -> None:
    """Test for sending fan mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


@pytest.mark.parametrize(
    "fan_mode",
    (FAN_AUTO, FAN_LOW, FAN_MEDIUM_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH),
)
async def test_update_fan_mode(
    hass: HomeAssistant, discovery, device, mock_now, fan_mode
) -> None:
    """Test for updating fan mode from the device."""
    device().fan_speed = FAN_MODES_REVERSE.get(fan_mode)

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


@pytest.mark.parametrize(
    "swing_mode", (SWING_OFF, SWING_BOTH, SWING_VERTICAL, SWING_HORIZONTAL)
)
async def test_send_swing_mode(
    hass: HomeAssistant, discovery, device, mock_now, swing_mode
) -> None:
    """Test for sending swing mode command to the device."""
    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: swing_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) == swing_mode


async def test_send_invalid_swing_mode(
    hass: HomeAssistant, discovery, device, mock_now
) -> None:
    """Test for sending swing mode command to the device."""
    await async_setup_gree(hass)

    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "invalid"},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) != "invalid"


@pytest.mark.parametrize(
    "swing_mode", (SWING_OFF, SWING_BOTH, SWING_VERTICAL, SWING_HORIZONTAL)
)
async def test_send_swing_mode_device_timeout(
    hass: HomeAssistant, discovery, device, mock_now, swing_mode
) -> None:
    """Test for sending swing mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: swing_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) == swing_mode


@pytest.mark.parametrize(
    "swing_mode", (SWING_OFF, SWING_BOTH, SWING_VERTICAL, SWING_HORIZONTAL)
)
async def test_update_swing_mode(
    hass: HomeAssistant, discovery, device, mock_now, swing_mode
) -> None:
    """Test for updating swing mode from the device."""
    device().horizontal_swing = (
        HorizontalSwing.FullSwing
        if swing_mode in (SWING_BOTH, SWING_HORIZONTAL)
        else HorizontalSwing.Default
    )
    device().vertical_swing = (
        VerticalSwing.FullSwing
        if swing_mode in (SWING_BOTH, SWING_VERTICAL)
        else VerticalSwing.Default
    )

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) == swing_mode


async def test_name(hass: HomeAssistant, discovery, device) -> None:
    """Test for name property."""
    await async_setup_gree(hass)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake-device-1"


async def test_supported_features_with_turnon(
    hass: HomeAssistant, discovery, device
) -> None:
    """Test for supported_features property."""
    await async_setup_gree(hass)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
    )
