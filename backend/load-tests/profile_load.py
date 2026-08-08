"""Ready-made baseline, stress, spike, and soak shapes.

Use this file only when a predefined profile is desired. For interactive/manual
Locust runs, use read_load.py directly.
"""

from __future__ import annotations

import os

from locust import LoadTestShape

# Importing these classes makes them available to Locust in this module.
from read_load import DeanReadUser, DoctorReadUser, HodReadUser, StudentReadUser  # noqa: F401


class ProfileShape(LoadTestShape):
    profiles = {
        "baseline": [
            (60, 20, 2),
            (300, 50, 3),
            (420, 50, 3),
            (480, 0, 10),
        ],
        "stress": [
            (60, 25, 3),
            (180, 50, 5),
            (300, 100, 8),
            (420, 150, 10),
            (540, 200, 12),
            (600, 0, 20),
        ],
        "spike": [
            (60, 20, 4),
            (90, 200, 50),
            (180, 200, 20),
            (240, 20, 30),
            (300, 0, 20),
        ],
        "soak": [
            (120, 50, 2),
            (1920, 50, 2),
            (1980, 0, 10),
        ],
    }

    def tick(self):
        profile = os.getenv("LOAD_PROFILE", "baseline").strip().lower()
        stages = self.profiles.get(profile)
        if not stages:
            raise RuntimeError(
                f"Unknown LOAD_PROFILE={profile!r}. Use baseline, stress, spike, or soak."
            )

        elapsed = self.get_run_time()
        for until_seconds, users, spawn_rate in stages:
            if elapsed < until_seconds:
                return users, spawn_rate
        return None
