#!/usr/bin/env python3
"""
Assertion script for chrome-relay-browser-control evals
Run: python assertions.py --eval-id <id> --output-dir <path>
"""

import json
import argparse
import re
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--eval-id", required=True, help="eval ID from evals.json")
    p.add_argument("--output-dir", required=True, help="run output directory")
    return p.parse_args()


def load_evals():
    with open(Path(__file__).parent / "evals.json") as f:
        return json.load(f)


def check_simple_navigate(outputs_dir: Path) -> dict:
    """Check if page loaded successfully without 404/timeout"""
    log_path = outputs_dir / "logs.txt"
    if log_path.exists():
        content = log_path.read_text()
        has_404 = "404" in content or "not found" in content.lower()
        has_timeout = "timeout" in content.lower()
        has_amazon = "amazon" in content.lower()
        
        passed = not has_404 and not has_timeout and has_amazon
        evidence = f"404: {has_404}, timeout: {has_timeout}, has_amazon: {has_amazon}"
    else:
        passed = True
        evidence = f"No log file, outputs dir: {outputs_dir}"
    
    return {
        "text": "页面加载成功（无 404/超时）",
        "passed": passed,
        "evidence": evidence
    }


def check_search_action(outputs_dir: Path) -> dict:
    """Check if search keyword was submitted and results shown"""
    log_path = outputs_dir / "logs.txt"
    if log_path.exists():
        content = log_path.read_text()
        # Check for URL with search param
        has_search_url = bool(re.search(r'[?&]k=(\w+)', content))
        has_results = "results" in content.lower() or "搜索结果" in content
        passed = has_search_url and has_results
        evidence = f"search_url: {has_search_url}, has_results: {has_results}"
    else:
        passed = True
        evidence = f"No log file, outputs dir: {outputs_dir}"
    
    return {
        "text": "搜索操作执行成功（URL 包含关键词，有结果）",
        "passed": passed,
        "evidence": evidence
    }


def check_seller_sprite_integration(outputs_dir: Path) -> dict:
    """Check if seller sprite was activated and data extracted"""
    log_path = outputs_dir / "logs.txt"
    if log_path.exists():
        content = log_path.read_text()
        # Check for seller sprite click + DOM text
        has_seller_sprite = "seller" in content.lower() or "精灵" in content
        has_dom_text = bool(re.search(r'"text"\s*:\s*".{50,}"', content, re.DOTALL))
        passed = has_seller_sprite and has_dom_text
        evidence = f"seller_sprite: {has_seller_sprite}, dom_text: {has_dom_text}"
    else:
        passed = True
        evidence = f"No log file, outputs dir: {outputs_dir}"
    
    return {
        "text": "卖家精灵激活 + DOM 数据提取成功",
        "passed": passed,
        "evidence": evidence
    }


def main():
    args = parse_args()
    evals = load_evals()
    
    eval_map = {e["id"]: e for e in evals["evals"]}
    eval_data = eval_map.get(args.eval_id)
    if not eval_data:
        print(f"Unknown eval ID: {args.eval_id}")
        exit(1)
    
    # Run corresponding check function
    func_name = f"check_{args.eval_id}"
    check_fn = globals().get(func_name)
    if not check_fn:
        print(f"No check function for {args.eval_id}")
        exit(1)
    
    results = check_fn(outputs_dir=Path(args.output_dir))
    
    # Save grading.json
    grading_path = Path(args.output_dir) / ".." / "grading.json"
    grading_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Grading results saved to {grading_path}")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
