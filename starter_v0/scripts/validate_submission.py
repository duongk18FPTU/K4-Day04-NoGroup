from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import TOOL_FUNCTIONS, load_tool_declarations


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    prompt_path = ROOT / "artifacts" / "system_prompt.md"
    tools_path = ROOT / "artifacts" / "tools.yaml"
    group_path = ROOT / "data" / "eval_group.json"
    app_path = ROOT / "app.py"
    report_path = ROOT / "artifacts" / "REPORT.md"
    version_log_path = ROOT / "artifacts" / "version_log.csv"

    for path in (prompt_path, tools_path, group_path, app_path, report_path, version_log_path):
        require(path.exists() and path.stat().st_size > 0, f"Missing deliverable: {path.relative_to(ROOT)}")

    declarations = load_tool_declarations(tools_path)
    declared_names = {item["name"] for item in declarations}
    require(declared_names == set(TOOL_FUNCTIONS), "tools.yaml names differ from the runtime registry")
    for declaration in declarations:
        name = declaration["name"]
        parameters = declaration["parameters"]
        require(parameters.get("type") == "object", f"{name}: parameters must be an object")
        require(parameters.get("additionalProperties") is False, f"{name}: schema must reject extra arguments")
        function_parameters = set(inspect.signature(TOOL_FUNCTIONS[name]).parameters)
        schema_parameters = set(parameters.get("properties", {}))
        require(schema_parameters == function_parameters, f"{name}: schema and implementation arguments differ")

    dataset = json.loads(group_path.read_text(encoding="utf-8"))
    cases = dataset.get("cases", [])
    single = [case for case in cases if "query" in case and "turns" not in case]
    multi = [case for case in cases if "turns" in case and "query" not in case]
    require(len(cases) == 10, "Group eval must contain exactly 10 cases")
    require(len(single) == 5 and len(multi) == 5, "Group eval must contain 5 single-turn and 5 multi-turn cases")
    require(len({case["id"] for case in cases}) == 10, "Group eval IDs must be unique")

    prompt = prompt_path.read_text(encoding="utf-8")
    for forbidden_case_id in ("H01", "M01", "E01", "A01", "G01"):
        require(forbidden_case_id not in prompt, "Final prompt must not hard-code eval case IDs")

    print("PASS: deliverables present")
    print(f"PASS: {len(declarations)} tool declarations match the runtime registry and signatures")
    print("PASS: group eval contains 5 single-turn and 5 multi-turn original cases")
    print("PASS: final prompt does not hard-code eval case IDs")


if __name__ == "__main__":
    main()
