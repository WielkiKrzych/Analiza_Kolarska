"""
Frontend State Management.

Centralized state manager to handle Session State with type safety.
"""
import streamlit as st
from modules.settings import SettingsManager

# Manual threshold inputs kept alive across tab switches
MANUAL_INPUT_KEYS = (
    "manual_vt1_watts", "manual_vt2_watts",
    "vt1_hr", "vt1_ve", "vt1_br", "vt2_hr", "vt2_ve", "vt2_br",
    "ve_breakpoint_manual", "test_start_power", "test_end_power",
    "test_duration",
    "smo2_lt1_m", "smo2_lt2_m", "smo2_lt1_smo2_m",
    "smo2_lt2_smo2_m", "reoxy_halftime_manual",
    "cci_breakpoint_manual",
)

class StateManager:
    """Manages application state and settings."""
    
    def __init__(self):
        self.settings_manager = SettingsManager()
        self._keys_map = {
            "weight": "rider_weight",
            "height": "rider_height", 
            "age": "rider_age",
            "gender_m": "is_male",
            "vt1_w": "vt1_watts",
            "vt2_w": "vt2_watts",
            "vt1_v": "vt1_vent",
            "vt2_v": "vt2_vent",
            "cp_in": "cp",
            "wp_in": "w_prime",
            "crank": "crank_length"
        }

    def init_session_state(self) -> None:
        """Seed missing session keys from the settings defaults.

        Existing values win, so values entered in the sidebar survive the rerun
        triggered by pressing Enter (Streamlit reruns the whole script and a
        blind overlay would reset them to the defaults).
        """
        saved_settings = self.settings_manager.load_settings()

        for ui_key, json_key in self._keys_map.items():
            if ui_key not in st.session_state and json_key in saved_settings:
                st.session_state[ui_key] = saved_settings[json_key]

        if 'report_generation_requested' not in st.session_state:
            st.session_state['report_generation_requested'] = False

    def cleanup_old_data(self) -> None:
        """Clean up old DataFrames from session state."""
        keys_to_check = ['_prev_df_plot', '_prev_df_resampled', '_prev_file_name', 'data_loaded']
        for key in keys_to_check:
            if key in st.session_state:
                del st.session_state[key]
                
    def preserve_widget_state(self, keys) -> None:
        """Keep widget values alive while their tab is not rendered.

        Streamlit drops a keyed widget's value at the end of any run in which the widget
        is not rendered; re-assigning the key detaches it from that cleanup.
        """
        for key in keys:
            if key in st.session_state:
                st.session_state[key] = st.session_state[key]

    def reset_manual_inputs(self) -> None:
        """Forget manual threshold inputs so a new file starts from its auto-detected values."""
        for key in MANUAL_INPUT_KEYS:
            st.session_state.pop(key, None)

    def set_data_loaded(self) -> None:
        st.session_state['data_loaded'] = True
        
    def is_data_loaded(self) -> bool:
        return st.session_state.get('data_loaded', False)
