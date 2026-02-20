from api.appointments.cancellation_notifications import build_cancellation_parameters


def test_build_cancellation_parameters_standard_four():
    params = build_cancellation_parameters(
        4,
        user_name="Ana",
        company_name="Clínica Sol",
        appointment_date="viernes 20 de febrero 2026",
        appointment_time="03:30 PM",
    )
    assert params == ["Ana", "Clínica Sol", "viernes 20 de febrero 2026", "03:30 PM"]


def test_build_cancellation_parameters_respects_expected_count():
    params = build_cancellation_parameters(
        2,
        user_name="Ana",
        company_name="Clínica Sol",
        appointment_date="x",
        appointment_time="y",
    )
    assert params == ["Ana", "Clínica Sol"]


def test_build_cancellation_parameters_fills_missing_values():
    params = build_cancellation_parameters(
        4,
        user_name="",
        company_name="",
        appointment_date="",
        appointment_time="",
    )
    assert params == ["Cliente", "su empresa", "Fecha por confirmar", "Hora por confirmar"]
