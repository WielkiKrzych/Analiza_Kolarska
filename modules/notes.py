import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class TrainingNotes:
    """Zarządzanie notatkami do treningów"""

    NOTES_DIR = Path(__file__).resolve().parent.parent / 'training_notes'

    def __init__(self):
        self.NOTES_DIR.mkdir(exist_ok=True)

    def get_notes_file(self, training_file: str) -> Path:
        """Pobierz plik notatek dla danego treningu.

        Sanitizes the filename to prevent path traversal attacks.
        """
        stem = Path(training_file).stem
        # Strip path separators and parent-directory references to prevent traversal
        safe_stem = stem.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self.NOTES_DIR / f"{safe_stem}_notes.json"

    def load_notes(self, training_file: str) -> dict:
        """Załaduj notatki z JSON"""
        notes_file = self.get_notes_file(training_file)
        if notes_file.exists():
            try:
                with open(notes_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load notes from {notes_file}: {e}")
                return {"training_file": training_file, "notes": []}
        return {"training_file": training_file, "notes": []}

    def save_notes(self, training_file: str, notes_data: dict) -> bool:
        """Zapisz notatki do JSON.

        Returns:
            True if saved successfully, False otherwise.
        """
        notes_file = self.get_notes_file(training_file)
        try:
            with open(notes_file, 'w', encoding='utf-8') as f:
                json.dump(notes_data, f, indent=2, ensure_ascii=False)
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to save notes to {notes_file}: {e}")
            return False

    def add_note(self, training_file: str, time_minute: float, metric: str, text: str) -> dict:
        """Dodaj notatkę"""
        notes_data = self.load_notes(training_file)

        note = {
            "time_minute": float(time_minute),
            "metric": metric,
            "text": text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        notes_data["notes"].append(note)
        self.save_notes(training_file, notes_data)
        return note

    def get_notes_for_metric(self, training_file: str, metric: str) -> list:
        """Pobierz notatki dla konkretnej metryki"""
        notes_data = self.load_notes(training_file)
        return [n for n in notes_data["notes"] if n["metric"] == metric]

    def delete_note(self, training_file: str, note_index: int) -> bool:
        """Usuń notatkę"""
        notes_data = self.load_notes(training_file)
        if 0 <= note_index < len(notes_data["notes"]):
            notes_data["notes"].pop(note_index)
            self.save_notes(training_file, notes_data)
            return True
        return False
