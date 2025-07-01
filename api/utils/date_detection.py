# api/utils/date_detection.py

import re
from datetime import datetime
import dateparser

def extract_datetime_from_text(question: str) -> datetime | None:
    """
    Intenta extraer un datetime desde texto en español usando varias estrategias:
    1. Formato ISO
    2. Formato '06-09-2025 | 09:00 AM'
    3. Formato '06/09/2025 09:00 AM'
    4. Texto libre con dateparser ('lunes 10 de junio a las 4 PM')
    """

    # 1. Formato ISO (completo)
    iso_match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:-\d{2}:\d{2})?", question)
    if iso_match:
        try:
            return datetime.fromisoformat(iso_match.group())
        except Exception:
            pass

    # 2. Formato visual tipo '06-09-2025 | 09:00 AM'
    visual_match = re.search(
        r"(\d{2}[-/]\d{2}[-/]\d{4})\s*(?:\||a las)?\s*(\d{1,2}:\d{2}\s*[APMapm\.]{2,4})",
        question
    )
    if visual_match:
        try:
            date_part, time_part = visual_match.groups()
            datetime_str = f"{date_part} {time_part}"
            try:
                return datetime.strptime(datetime_str, "%d-%m-%Y %I:%M %p")
            except ValueError:
                return datetime.strptime(datetime_str, "%m-%d-%Y %I:%M %p")
        except Exception:
            pass

    # 3. Texto libre con dateparser (última opción)
    parsed = dateparser.parse(question, languages=['es'])
    if parsed:
        return parsed

    return None
