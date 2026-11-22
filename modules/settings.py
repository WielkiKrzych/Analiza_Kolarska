SETTINGS_FILE = 'user_settings.json'

class SettingsManager:
    def __init__(self, file_path=SETTINGS_FILE):
        self.file_path = file_path
        self.default_settings = {
            "rider_weight": 97.0,
            "rider_height": 180,
            "rider_age": 30,
            "is_male": True,
            "cp": 380,
            "w_prime": 15600,
            "vt1_watts": 310,
            "vt2_watts": 360,
            "vt1_vent": 73.0,
            "vt2_vent": 105.0,
            "crank_length": 165.0
        }

    def load_settings(self):
        """Returns hardcoded default settings, ignoring any saved file to enforce user preferences."""
        # Always return defaults to ensure consistent startup state as requested
        return self.default_settings
