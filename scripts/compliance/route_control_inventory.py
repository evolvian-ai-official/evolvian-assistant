#!/usr/bin/env python3
"""
Build an endpoint inventory with a lightweight auth/control classification.

Usage:
  python scripts/compliance/route_control_inventory.py \
    --api-root api \
    --out docs/compliance/endpoint_control_inventory.csv
"""

from __future__ import annotations

import argparse
import ast
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}
AUTH_CALLS = {
    "authorize_client_request",
    "get_current_user_id",
    "require_internal_request",
    "has_valid_internal_token",
    "verify_meta_signature",
    "verify_twilio_signature",
    "_load_template_with_auth",
}
TOKEN_HEADER_HINTS = {
    "x-reset-token",
    "x-evolvian-internal-token",
}
WEBHOOK_HEADER_HINTS = {
    "x-evolvian-signature",
    "x-hub-signature-256",
    "x-twilio-signature",
}
PUBLIC_ROUTE_PREFIXES = (
    "/api/public/",
    "/webhooks/",
    "/api/whatsapp/webhook",
    "/api/blog/",
    "/embed",
    "/embed.js",
    "/embed-floating",
    "/widget/",
    "/widget.html",
    "/chat",
    "/chat-widget",
    "/check_email_exists",
    "/check_consent",
    "/register_consent",
    "/meta_approved_templates",
    "/terms",
    "/privacy",
)


@dataclass
class EndpointRow:
    file_path: str
    line: int
    function: str
    method: str
    route: str
    auth_control: str
    has_auth_control: str
    review_flag: str


def _literal_str(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _router_prefixes(module: ast.Module) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        target = node.targets[0].id
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Name) or call.func.id != "APIRouter":
            continue

        prefix = ""
        for kw in call.keywords:
            if kw.arg == "prefix":
                prefix = _literal_str(kw.value) or ""
                break
        prefixes[target] = prefix
    return prefixes


def _call_name(call: ast.Call) -> str | None:
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return None


def _collect_function_calls(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    calls: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name:
                calls.add(name)
    return calls


def _collect_string_literals(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    literals: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add(node.value.strip().lower())
    return literals


def _classify_control(route: str, calls: set[str], literals: set[str]) -> str:
    if "require_internal_request" in calls:
        return "internal_token"
    if "verify_meta_signature" in calls:
        return "webhook_signature"
    if "verify_twilio_signature" in calls:
        return "webhook_signature"
    if "authorize_client_request" in calls:
        return "auth_client_ownership"
    if "get_current_user_id" in calls:
        return "auth_user"
    if "_load_template_with_auth" in calls:
        return "auth_client_ownership"
    if any(header in literals for header in TOKEN_HEADER_HINTS):
        return "internal_token"
    if any(header in literals for header in WEBHOOK_HEADER_HINTS):
        return "webhook_signature"
    if "callback" in route and ("google_calendar" in route or "gmail_oauth" in route):
        return "oauth_callback_handshake"
    if route == "/stripe":
        return "webhook_signature"

    if any(route.startswith(prefix) for prefix in PUBLIC_ROUTE_PREFIXES):
        return "public_or_webhook_entrypoint"

    return "none_detected"


def _iter_endpoint_rows(py_file: Path) -> Iterable[EndpointRow]:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return

    prefixes = _router_prefixes(tree)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        calls = _collect_function_calls(node)
        literals = _collect_string_literals(node)
        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call):
                continue
            if not isinstance(deco.func, ast.Attribute):
                continue
            if deco.func.attr not in HTTP_METHODS:
                continue
            if not isinstance(deco.func.value, ast.Name):
                continue

            router_name = deco.func.value.id
            prefix = prefixes.get(router_name, "")
            route_part = _literal_str(deco.args[0]) if deco.args else ""
            route = f"{prefix}{route_part or ''}" or "/"
            method = deco.func.attr.upper()

            control = _classify_control(route, calls, literals)
            has_auth = "yes" if control != "none_detected" else "no"
            review_flag = "review_required" if control == "none_detected" else ""

            yield EndpointRow(
                file_path=str(py_file),
                line=node.lineno,
                function=node.name,
                method=method,
                route=route,
                auth_control=control,
                has_auth_control=has_auth,
                review_flag=review_flag,
            )


def build_inventory(api_root: Path) -> list[EndpointRow]:
    rows: list[EndpointRow] = []
    for py_file in sorted(api_root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        rows.extend(_iter_endpoint_rows(py_file))
    rows.sort(key=lambda r: (r.route, r.method, r.file_path, r.line))
    return rows


def write_csv(rows: list[EndpointRow], out_file: Path) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "file_path",
                "line",
                "function",
                "method",
                "route",
                "auth_control",
                "has_auth_control",
                "review_flag",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.file_path,
                    row.line,
                    row.function,
                    row.method,
                    row.route,
                    row.auth_control,
                    row.has_auth_control,
                    row.review_flag,
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate route control inventory CSV")
    parser.add_argument("--api-root", default="api", help="API folder root")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    api_root = Path(args.api_root)
    out_file = Path(args.out)

    rows = build_inventory(api_root)
    write_csv(rows, out_file)
    print(f"Inventory generated: {out_file} ({len(rows)} endpoints)")


if __name__ == "__main__":
    main()
