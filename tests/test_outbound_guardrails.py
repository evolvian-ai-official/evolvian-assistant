import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


GUARDED_ENTRYPOINTS = [
    (
        "api/modules/whatsapp/whatsapp_sender.py",
        "send_whatsapp_message_for_client",
        {"evaluate_outbound_policy", "log_outbound_policy_event"},
    ),
    (
        "api/modules/whatsapp/whatsapp_sender.py",
        "send_whatsapp_template_for_client",
        {"evaluate_outbound_policy", "log_outbound_policy_event"},
    ),
    (
        "api/modules/calendar/send_confirmation_email.py",
        "send_confirmation_email",
        {"begin_email_send_audit", "complete_email_send_audit"},
    ),
    (
        "api/modules/calendar/notify_business_owner.py",
        "notify_business_owner",
        {"begin_email_send_audit", "complete_email_send_audit"},
    ),
    (
        "api/modules/calendar/schedule_event.py",
        "schedule_event",
        {"begin_email_send_audit", "complete_email_send_audit"},
    ),
    (
        "api/modules/email_integration/gmail_oauth.py",
        "send_reply",
        {"begin_email_send_audit", "complete_email_send_audit", "ensure_marketing_footer"},
    ),
    (
        "api/modules/email_integration/gmail_webhook.py",
        "process_gmail_message",
        {"begin_email_send_audit", "complete_email_send_audit"},
    ),
    (
        "api/appointments/message_templates.py",
        "create_message_template",
        {"is_marketing_template_type", "validate_marketing_template_body"},
    ),
    (
        "api/appointments/message_templates.py",
        "update_message_template",
        {"is_marketing_template_type", "validate_marketing_template_body"},
    ),
]


def _parse_module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _find_function(module: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"Function {name!r} not found")


def _called_names(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if isinstance(callee, ast.Name):
            names.add(callee.id)
        elif isinstance(callee, ast.Attribute):
            names.add(callee.attr)
    return names


def test_outbound_entrypoints_keep_policy_hooks():
    failures: list[str] = []

    for relative_path, function_name, required_calls in GUARDED_ENTRYPOINTS:
        path = REPO_ROOT / relative_path
        module = _parse_module(path)
        function_node = _find_function(module, function_name)
        calls = _called_names(function_node)
        missing = sorted(required_calls - calls)
        if missing:
            failures.append(
                f"{relative_path}:{function_name} missing policy hook calls: {', '.join(missing)}"
            )

    assert not failures, "\n".join(failures)
