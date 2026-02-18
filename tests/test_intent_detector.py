import unittest

from api.modules.assistant_rag.intent_detector import detect_intent_to_schedule


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


if __name__ == "__main__":
    unittest.main()
