"""
Durability/Fatigue Resistance Analysis Module.
Implements durability index and related metrics based on 2020-2026 literature.
"""

from typing import Optional, Tuple
import pandas as pd

from .common import ensure_pandas


def calculate_durability_index(
    df: pd.DataFrame, 
    min_duration_min: int = 20,
    method: str = "half"
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Calculate Durability Index - power sustainability over workout.
    
    Based on recent research (2020-2026) showing durability as key predictor
    of endurance performance, especially in long-course triathlon and cycling.
    
    Methods:
    - "half": Compare first half vs second half (standard)
    - "thirds": Compare first third vs last third (more sensitive to late fatigue)
    - "quarter": Compare first quarter vs last quarter (early vs late fatigue)
    
    DI = (Avg Power Later Period / Avg Power Early Period) * 100
    
    Args:
        df: DataFrame with 'watts' column
        min_duration_min: Minimum workout duration in minutes
        method: Method for splitting data ("half", "thirds", "quarter")
        
    Returns:
        Tuple of (durability_index, early_avg, late_avg)
        Returns (None, None, None) if insufficient data
    """
    
    df = ensure_pandas(df)
    
    if df is None or "watts" not in df.columns:
        return None, None, None
    
    # Need minimum duration
    min_samples = min_duration_min * 60  # assuming 1Hz data
    if len(df) < min_samples:
        return None, None, None
    
    # Split data based on method
    if method == "half":
        midpoint = len(df) // 2
        early_half = df.iloc[:midpoint]
        late_half = df.iloc[midpoint:]
    elif method == "thirds":
        third = len(df) // 3
        early_third = df.iloc[:third]
        late_third = df.iloc[-third:] if third > 0 else df.iloc[:0]
        early_half = early_third
        late_half = late_third
    elif method == "quarter":
        quarter = len(df) // 4
        early_quarter = df.iloc[:quarter]
        late_quarter = df.iloc[-quarter:] if quarter > 0 else df.iloc[:0]
        early_half = early_quarter
        late_half = late_quarter
    else:
        # Default to half
        midpoint = len(df) // 2
        early_half = df.iloc[:midpoint]
        late_half = df.iloc[midpoint:]
    
    # Calculate averages
    early_avg = early_half["watts"].mean()
    late_avg = late_half["watts"].mean()
    
    # Guard against division by zero
    if early_avg <= 0:
        return None, None, None
    
    durability = (late_avg / early_avg) * 100
    
    return round(durability, 1), round(early_avg, 0), round(late_avg, 0)


def get_durability_interpretation(di: float) -> str:
    """
    Get interpretation of Durability Index based on 2020-2026 research.
    
    Updated thresholds based on recent studies of elite endurance athletes.
    
    Args:
        di: Durability Index (percentage)
        
    Returns:
        Polish interpretation string with training implications
    """
    
    if di is None:
        return "❓ Brak danych do analizy wytrzymałościowej"
    
    # Updated based on Sporis et al. 2021, Jones et al. 2022, 
    # Sebranek et al. 2023 durability research in cyclists and triathletes
    elif di >= 98:
        return ("🟢 Fenomenalna wytrzymałość - poziom elity światowej klasy. "
                "Utrzymujesz moc praktycznie bez spadku mimo zmęczenia. "
                "To rzadka cecha występują u <1% wytrenowanych zawodników.")
    elif di >= 95:
        return ("🟢 Wyjątkowa wytrzymałość - charakterystyczna dla zawodowców WTour/Ironman pros. "
                "Minimalny spadek mocy wskazuje na doskonałą gospodarkę energetyczną "
                "i wysoki udział metabolizmu tlenowego nawet w stanie zmęczenia.")
    elif di >= 92:
        return ("🟢 Bardzo dobra wytrzymałość - poziom elity krajowej/continental. "
                "Utrzymujesz >92% mocy w drugiej połowie, co wskazuje na "
                "dobrą adaptację do długotrwałego wysiłku i niski koszt termiczny.")
    elif di >= 90:
        return ("🟡 Dobra wytrzymałość - poziom wytrenowanego amatora zaawansowanego. "
                "Utrzymujesz 90-95% mocy, co jest dobrym wynikiem, "
                "ale jest przestrzeń do poprawy w zakresie opóźnienia zmęczenia periferyjnego.")
    elif di >= 87:
        return ("🟠 Średnia wytrzymałość - typowa dla dobrze wytrenowanych amatorów. "
                "Spadek 87-90% sugeruje umiarkowane gromadzenie się metabolitów "
                "i/lub wzrost kosztu termicznego podczas długiego wysiłku.")
    elif di >= 83:
        return ("🟠 Umiarkowana wytrzymałość - wymaga pracy nad wytrzymałościową podstawą. "
                "Spadek 83-87% wskazuje na potrzebę zwiększenia objętości treningowej "
                "w strefie Z2 oraz pracy nad efektywnością ekonomiczną jazdy.")
    elif di >= 80:
        return ("🟠 Niska wytrzymałość - priorytet treningowy. "
                "Spadek poniżej 80% wymaga interwencji: więcej długich wyjazdów w Z2, "
                "praca nad techniką jazdy oraz strategią nawadniania i chłodzenia.")
    else:
        return ("🔴 Bardzo słaba wytrzymałość - wymaga kompleksowej pracy podstawowej. "
                "Spadek poniżej 80% sugeruje znaczne gromadzenie się zmęczenia periferyjnego, "
                "niską ujemność tlenową lub problemy z regulacją temperatury ciała. "
                "Zalecany blok podstawowy 8-12 tygodni z naciskiem na Z2 i technikę.")

