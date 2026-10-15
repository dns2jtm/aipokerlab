"""Integration test: OCR toggle updates the hand entry via the rta.py loop."""
import os
import sys
import time
import tkinter as tk
from unittest.mock import Mock
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class _DummyMemoryMonitor:
    def get_memory_usage_mb(self):
        return 0.0


class _DummySleepManager:
    is_sleeping = False

    def enable(self):
        pass

    def disable(self):
        pass


class MockOcr:
    def __init__(self):
        self.call_count = 0

    def capture_and_read(self, *args, **kwargs):
        self.call_count += 1
        return "AKs"

    def capture_and_read_with_position(self, *args, **kwargs):
        self.call_count += 1
        return {
            "hand": "AKs",
            "cards": ("As", "Ks"),
            "reliable": True,
            "table_id": 1,
            "table_name": None,
            "captured_at": time.monotonic(),
            "position": "BTN",
            "spot": "open",
        }

    def get_memory_monitor(self):
        return _DummyMemoryMonitor()

    def get_sleep_manager(self):
        return _DummySleepManager()


def test_ocr_integration(monkeypatch):
    import rta

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display is unavailable")
    root.withdraw()

    mock_ocr = MockOcr()
    monkeypatch.setattr(rta, "HAS_OCR", True)
    monkeypatch.setattr(rta, "ocr_module", mock_ocr)
    monkeypatch.setattr(rta, "HAS_MULTITABLE", False)
    monkeypatch.setattr(rta, "HAS_ANALYTICS", False)

    app = rta.RTAApp(root)
    app._play_sound = Mock()
    app._config["poll_interval_active"] = 0.05
    app.ocr_var.set(True)
    app._toggle_ocr()  # start OCR thread

    done = {}

    def check():
        done["hand"] = app.hand_entry.get()
        done["alive"] = app._ocr_thread is not None and app._ocr_thread.is_alive()
        done["status"] = app.ocr_status.cget("text")
        app._on_close()

    root.after(250, check)
    root.mainloop()

    assert done.get("hand") == "AKs", f"Expected 'AKs', got {done.get('hand')!r}"
    assert mock_ocr.call_count >= 2, "OCR loop should have polled at least twice"


if __name__ == "__main__":
    import rta

    root = tk.Tk()
    root.withdraw()
    mock_ocr = MockOcr()
    rta.HAS_OCR = True
    rta.ocr_module = mock_ocr
    rta.HAS_MULTITABLE = False
    rta.HAS_ANALYTICS = False
    app = rta.RTAApp(root)
    app._config["poll_interval_active"] = 0.2
    app.ocr_var.set(True)
    app._toggle_ocr()

    done = {}

    def check():
        done["hand"] = app.hand_entry.get()
        done["alive"] = app._ocr_thread.is_alive()
        done["status"] = app.ocr_status.cget("text")
        app._on_close()

    root.after(700, check)
    root.mainloop()

    print("capture_and_read calls:", mock_ocr.call_count, "(expected >= 2)")
    print("ocr thread alive:", done.get("alive"))
    print("ocr_status:", done.get("status"))
    print("hand after OCR:", repr(done.get("hand")))
    assert done.get("hand") == "AKs", f"Expected 'AKs', got {done.get('hand')!r}"
    assert mock_ocr.call_count >= 2, "OCR loop should have polled"
    print("INTEGRATION OK")
