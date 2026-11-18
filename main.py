import json
import os
import sys
from model import parse_curves, forecast


def process_case(case_path, output_dir):
    with open(case_path, "r", encoding="utf-8") as f:
        case = json.load(f)
    case_id = case["id"]
    hour1_print = case["known"][0]["viewers"]
    comparables = case["comparables"]
    curves = parse_curves(comparables)
    fc = forecast(hour1_print, curves)
    rows = []
    for hour in range(2, 25):
        rows.append({"hour": hour, "q": list(fc[hour])})
    out_obj = {"hours": rows}
    out_path = os.path.join(output_dir, f"{case_id}.out")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, separators=(",", ":"))


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.isdir(input_dir):
        return
    filenames = sorted([f for f in os.listdir(input_dir) if f.endswith(".in")])
    for filename in filenames:
        process_case(os.path.join(input_dir, filename), output_dir)


if __name__ == "__main__":
    main()
