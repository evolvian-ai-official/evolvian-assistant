import unittest
from datetime import date
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.modules.assistant_rag.intent_detector import (
    INTENT_CANCEL_APPOINTMENT,
    INTENT_CHECK_AVAILABILITY,
    INTENT_CONFIRM_APPOINTMENT,
    INTENT_CREATE_APPOINTMENT,
    INTENT_RESCHEDULE_APPOINTMENT,
    detect_appointment_intent,
    detect_intent_to_schedule,
    extract_appointment_entities,
)


class IntentDetectorTests(unittest.TestCase):
    def test_pricing_question_in_spanish_does_not_trigger_schedule(self):
        self.assertFalse(detect_intent_to_schedule("Qué planes tienes disponibles?"))

    def test_plans_information_question_does_not_trigger_schedule(self):
        self.assertFalse(detect_intent_to_schedule("Dame información sobre los planes disponibles"))

    def test_pricing_question_in_english_does_not_trigger_schedule(self):
        self.assertFalse(detect_intent_to_schedule("What plans are available?"))

    def test_booking_intent_in_spanish_triggers_schedule(self):
        self.assertTrue(detect_intent_to_schedule("Quiero agendar una cita para mañana"))

    def test_available_slots_in_english_triggers_schedule(self):
        self.assertTrue(detect_intent_to_schedule("Can you show available slots for tomorrow?"))

    def test_cancel_intent_is_classified(self):
        detected = detect_appointment_intent("Necesito cancelar mi cita de mañana")
        self.assertEqual(detected["intent"], INTENT_CANCEL_APPOINTMENT)

    def test_reschedule_intent_is_classified(self):
        detected = detect_appointment_intent("Quiero mover mi cita al viernes")
        self.assertEqual(detected["intent"], INTENT_RESCHEDULE_APPOINTMENT)

    def test_confirmation_intent_is_classified(self):
        detected = detect_appointment_intent("Perfecto, agéndalo")
        self.assertEqual(detected["intent"], INTENT_CONFIRM_APPOINTMENT)

    def test_create_intent_is_classified(self):
        detected = detect_appointment_intent("Quisiera una cita con ustedes")
        self.assertEqual(detected["intent"], INTENT_CREATE_APPOINTMENT)

    def test_check_availability_intent_is_classified(self):
        detected = detect_appointment_intent("¿Qué días tienen libre?")
        self.assertEqual(detected["intent"], INTENT_CHECK_AVAILABILITY)

    def test_entity_extraction_relative_day_time(self):
        entities = extract_appointment_entities("Quiero una cita mañana a las 3", reference_date=date(2026, 3, 9))
        self.assertEqual(entities.get("relative_date"), "tomorrow")
        self.assertEqual(entities.get("time"), "03:00")

    def test_entity_extraction_weekday_and_time_pm(self):
        entities = extract_appointment_entities("Puedes el viernes a las 12PM?", reference_date=date(2026, 3, 9))
        self.assertEqual(entities.get("day_of_week"), "friday")
        self.assertEqual(entities.get("time"), "12:00")

    def test_entity_extraction_iso_date(self):
        entities = extract_appointment_entities("Agenda para 2026-06-20 a las 10:30")
        self.assertEqual(entities.get("date"), "2026-06-20")
        self.assertEqual(entities.get("time"), "10:30")

    def test_entity_extraction_textual_date_spanish(self):
        entities = extract_appointment_entities(
            "Quiero una cita el 20 de junio",
            reference_date=date(2026, 3, 9),
        )
        self.assertEqual(entities.get("date"), "2026-06-20")


if __name__ == "__main__":
    unittest.main()
