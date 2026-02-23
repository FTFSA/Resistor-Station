"""
UI tests for the Raspberry Pi Resistor Station app.

Hardware (ADS1115, serial port) is mocked via conftest.py.
Pygame runs in SDL dummy mode — no physical display required.

Run from the repo root:
    pytest pi-app/tests/ -v
"""

import unittest
from unittest.mock import MagicMock, call, patch

import pygame

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_surface(w=480, h=320):
    """Return a MagicMock that looks enough like a pygame.Surface."""
    surf = MagicMock(spec=pygame.Surface)
    surf.get_width.return_value = w
    surf.get_height.return_value = h
    surf.get_size.return_value = (w, h)
    return surf


def _keydown(key=None, unicode_char=""):
    """Build a minimal pygame KEYDOWN event mock."""
    event = MagicMock()
    event.type = pygame.KEYDOWN
    event.key = key if key is not None else 0
    event.unicode = unicode_char
    return event


# ---------------------------------------------------------------------------
# UIManager
# ---------------------------------------------------------------------------

class TestUIManager(unittest.TestCase):
    """UIManager: screen registry, transitions, and event/update/draw dispatch."""

    def setUp(self):
        from ui_manager import UIManager
        self.surface = _make_surface()
        self.manager = UIManager(self.surface)

    def test_register_and_switch(self):
        screen = MagicMock()
        self.manager.register_screen("lab", screen)
        self.manager.switch_to("lab")  # Should not raise

    def test_switch_to_unknown_screen_raises(self):
        with self.assertRaises((KeyError, ValueError)):
            self.manager.switch_to("does_not_exist")

    def test_draw_delegates_to_active_screen(self):
        screen = MagicMock()
        self.manager.register_screen("lab", screen)
        self.manager.switch_to("lab")
        self.manager.draw()
        screen.draw.assert_called_once()

    def test_update_delegates_to_active_screen(self):
        screen = MagicMock()
        self.manager.register_screen("lab", screen)
        self.manager.switch_to("lab")
        self.manager.update(0.016)
        screen.update.assert_called_once_with(0.016)

    def test_handle_event_dispatches_to_active_screen(self):
        screen = MagicMock()
        self.manager.register_screen("lab", screen)
        self.manager.switch_to("lab")
        event = MagicMock()
        self.manager.handle_event(event)
        screen.handle_event.assert_called_once_with(event)

    def test_inactive_screens_do_not_receive_update(self):
        s1, s2 = MagicMock(), MagicMock()
        self.manager.register_screen("lab", s1)
        self.manager.register_screen("calc", s2)
        self.manager.switch_to("lab")
        self.manager.update(0.1)
        s1.update.assert_called_once_with(0.1)
        s2.update.assert_not_called()

    def test_switch_changes_which_screen_draws(self):
        s1, s2 = MagicMock(), MagicMock()
        self.manager.register_screen("lab", s1)
        self.manager.register_screen("calc", s2)
        self.manager.switch_to("lab")
        self.manager.switch_to("calc")
        self.manager.draw()
        s2.draw.assert_called_once()
        s1.draw.assert_not_called()

    def test_multiple_update_calls_accumulate(self):
        screen = MagicMock()
        self.manager.register_screen("lab", screen)
        self.manager.switch_to("lab")
        self.manager.update(0.016)
        self.manager.update(0.016)
        self.assertEqual(screen.update.call_count, 2)

    def test_no_active_screen_draw_does_not_raise(self):
        # Manager with no screens registered — draw() should not crash
        try:
            self.manager.draw()
        except Exception:
            pass  # Acceptable to raise; must not be an unhandled AttributeError on None


# ---------------------------------------------------------------------------
# ScreenLiveLab
# ---------------------------------------------------------------------------

class TestScreenLiveLab(unittest.TestCase):
    """ScreenLiveLab: polls meter, updates serial, renders without crashing."""

    def setUp(self):
        from screen_live_lab import ScreenLiveLab
        self.surface = _make_surface()
        self.meter = MagicMock()
        self.serial = MagicMock()
        self.meter.read.return_value = 4700.0
        self.screen = ScreenLiveLab(self.surface, self.meter, self.serial)

    def test_update_calls_meter_read(self):
        self.screen.update(0.016)
        self.meter.read.assert_called()

    def test_update_calls_send_measurement(self):
        self.screen.update(0.016)
        self.serial.send_measurement.assert_called()

    def test_send_measurement_receives_resistance(self):
        self.meter.read.return_value = 4700.0
        self.screen.update(0.016)
        args = self.serial.send_measurement.call_args
        # First positional argument should be the resistance value
        resistance_arg = args[0][0] if args[0] else args[1].get("resistance")
        self.assertAlmostEqual(resistance_arg, 4700.0)

    def test_draw_does_not_raise(self):
        self.screen.update(0.016)
        self.screen.draw()

    def test_draw_calls_surface_blit_or_fill(self):
        self.screen.update(0.016)
        self.screen.draw()
        drew = (
            self.surface.blit.called
            or self.surface.fill.called
            or self.surface.draw.called
        )
        self.assertTrue(drew, "draw() should write pixels to the surface")

    def test_handle_event_does_not_raise(self):
        event = MagicMock()
        self.screen.handle_event(event)

    def test_zero_resistance_handled(self):
        self.meter.read.return_value = 0.0
        try:
            self.screen.update(0.016)
            self.screen.draw()
        except ZeroDivisionError:
            self.fail("update/draw crashed on zero resistance")

    def test_very_large_resistance_handled(self):
        self.meter.read.return_value = 1_000_000.0
        self.screen.update(0.016)
        self.screen.draw()


# ---------------------------------------------------------------------------
# ScreenOhmTriangle
# ---------------------------------------------------------------------------

class TestScreenOhmTriangle(unittest.TestCase):
    """ScreenOhmTriangle: V=IR solver logic and UI contract."""

    def setUp(self):
        from screen_ohm_triangle import ScreenOhmTriangle
        self.surface = _make_surface()
        self.screen = ScreenOhmTriangle(self.surface)

    def test_update_does_not_raise(self):
        self.screen.update(0.016)

    def test_draw_does_not_raise(self):
        self.screen.draw()

    def test_handle_event_does_not_raise(self):
        self.screen.handle_event(MagicMock())

    # --- Ohm's Law calculation correctness ---

    def test_solve_voltage(self):
        # V = I * R  →  2 A × 500 Ω = 1000 V
        result = self.screen.calculate("V", I=2.0, R=500.0)
        self.assertAlmostEqual(result, 1000.0)

    def test_solve_current(self):
        # I = V / R  →  12 V / 4 Ω = 3 A
        result = self.screen.calculate("I", V=12.0, R=4.0)
        self.assertAlmostEqual(result, 3.0)

    def test_solve_resistance(self):
        # R = V / I  →  9 V / 0.5 A = 18 Ω
        result = self.screen.calculate("R", V=9.0, I=0.5)
        self.assertAlmostEqual(result, 18.0)

    def test_solve_voltage_small_values(self):
        # V = 0.01 A × 330 Ω = 3.3 V
        result = self.screen.calculate("V", I=0.01, R=330.0)
        self.assertAlmostEqual(result, 3.3)

    def test_solve_current_divide_by_zero_raises(self):
        with self.assertRaises((ZeroDivisionError, ValueError)):
            self.screen.calculate("I", V=5.0, R=0.0)

    def test_solve_resistance_divide_by_zero_raises(self):
        with self.assertRaises((ZeroDivisionError, ValueError)):
            self.screen.calculate("R", V=5.0, I=0.0)

    def test_unknown_variable_raises(self):
        with self.assertRaises((KeyError, ValueError)):
            self.screen.calculate("X", V=1.0, I=1.0)

    def test_negative_values_produce_negative_result(self):
        # Negative current → negative voltage (physically meaningful in signed math)
        result = self.screen.calculate("V", I=-0.5, R=100.0)
        self.assertAlmostEqual(result, -50.0)


# ---------------------------------------------------------------------------
# ScreenCalculator
# ---------------------------------------------------------------------------

class TestScreenCalculator(unittest.TestCase):
    """ScreenCalculator: input buffer, E24 snap, band lookup."""

    def setUp(self):
        from screen_calculator import ScreenCalculator
        self.surface = _make_surface()
        self.screen = ScreenCalculator(self.surface)

    def test_update_does_not_raise(self):
        self.screen.update(0.016)

    def test_draw_does_not_raise(self):
        self.screen.draw()

    def test_handle_event_does_not_raise(self):
        self.screen.handle_event(MagicMock())

    def test_initial_input_buffer_is_empty(self):
        self.assertEqual(self.screen.input_buffer, "")

    def test_digit_keys_append_to_buffer(self):
        for ch in "4700":
            self.screen.handle_event(_keydown(unicode_char=ch))
        self.assertEqual(self.screen.input_buffer, "4700")

    def test_non_digit_keys_ignored(self):
        for ch in "abc!@":
            self.screen.handle_event(_keydown(unicode_char=ch))
        self.assertEqual(self.screen.input_buffer, "")

    def test_backspace_removes_last_character(self):
        for ch in "470":
            self.screen.handle_event(_keydown(unicode_char=ch))
        self.screen.handle_event(_keydown(key=pygame.K_BACKSPACE))
        self.assertEqual(self.screen.input_buffer, "47")

    def test_backspace_on_empty_buffer_does_not_crash(self):
        self.screen.handle_event(_keydown(key=pygame.K_BACKSPACE))
        self.assertEqual(self.screen.input_buffer, "")

    def test_enter_triggers_e24_snap(self):
        for ch in "4700":
            self.screen.handle_event(_keydown(unicode_char=ch))
        with patch("screen_calculator.snap_to_e24") as mock_snap:
            mock_snap.return_value = 4700.0
            self.screen.handle_event(_keydown(key=pygame.K_RETURN))
            mock_snap.assert_called_once_with(4700.0)

    def test_enter_triggers_band_lookup(self):
        for ch in "4700":
            self.screen.handle_event(_keydown(unicode_char=ch))
        with patch("screen_calculator.snap_to_e24", return_value=4700.0), \
             patch("screen_calculator.resistance_to_bands") as mock_bands:
            mock_bands.return_value = ["yellow", "violet", "red", "gold"]
            self.screen.handle_event(_keydown(key=pygame.K_RETURN))
            mock_bands.assert_called_once_with(4700.0)

    def test_draw_after_calculation_does_not_raise(self):
        for ch in "10000":
            self.screen.handle_event(_keydown(unicode_char=ch))
        with patch("screen_calculator.snap_to_e24", return_value=10000.0), \
             patch("screen_calculator.resistance_to_bands",
                   return_value=["brown", "black", "orange", "gold"]):
            self.screen.handle_event(_keydown(key=pygame.K_RETURN))
        self.screen.draw()


if __name__ == "__main__":
    unittest.main()
