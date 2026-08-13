import argparse
import csv
import getpass
import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
import httpx
RESULT_FIELDS = (
    "run_id,question_id,category,file_format,repeat_index,session_id,question,expected_sources,"
    "should_refuse,http_status,answer,returned_sources,required_keyword_coverage,missing_required_keywords,"
    "forbidden_keywords_found,source_pass,refusal_pass,total_ms,manual_correctness,manual_completeness,"
    "manual_confusion,manual_notes,error,tested_at"
).split(",")
def split_values(text): return [item.strip() for item in text.split("||") if item.strip()]
def load_questions(csv_path, selected_text):
    """读取启用题目，并按可选题号筛选"""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    selected_ids = {item.strip().upper() for item in selected_text.split(",") if item.strip()}
    enabled_rows = [row for row in rows if row["enabled"].strip().lower() == "true"]
    missing_ids = selected_ids - {row["question_id"] for row in enabled_rows}
    if missing_ids: raise ValueError(f"题号不存在或未启用：{', '.join(sorted(missing_ids))}")
    questions = [row for row in enabled_rows if not selected_ids or row["question_id"] in selected_ids]
    for row in questions:
        if int(row["repeat_count"]) < 1: raise ValueError(f"{row['question_id']}的repeat_count必须大于0")
    return questions
def login(client, base_url, username, password):
    """使用表单登录，只在内存中返回JWT"""
    response = client.post(f"{base_url}/api/auth/login", data={"username": username, "password": password})
    if response.status_code != 200: raise RuntimeError(f"登录失败，HTTP {response.status_code}：{response.text[:300]}")
    token = response.json().get("access_token", "")
    if not token: raise RuntimeError("登录响应中没有access_token")
    return token
def send_chat(client, base_url, token, query, session_id):
    """按照前端逻辑读取SSE并拼接完整回答"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"query": query, "session_id": session_id}
    answer, received_done = "", False
    with client.stream("POST", f"{base_url}/api/chat/completions", headers=headers, json=body) as response:
        if response.status_code != 200:
            response.read()
            return response.status_code, "", f"HTTP {response.status_code}：{response.text[:300]}"
        for line in response.iter_lines():
            if not line.startswith("data: "): continue
            data_text = line[6:].strip()
            if data_text == "[DONE]":
                received_done = True
                break
            try:
                data = json.loads(data_text)
            except json.JSONDecodeError as error:
                return response.status_code, answer, f"SSE数据解析失败：{error}"
            if data.get("content"): answer += data["content"]
    if not received_done: return 200, answer, "SSE未收到[DONE]结束标记"
    if not answer: return 200, "", "SSE结束但回答为空"
    return 200, answer, ""
def analyze_answer(question, answer):
    """计算关键词辅助指标，并谨慎提取参考来源"""
    required = split_values(question["required_answer_keywords"])
    forbidden = split_values(question["forbidden_answer_keywords"])
    answer_lower = answer.casefold()
    missing = [item for item in required if item.casefold() not in answer_lower]
    forbidden_found = [item for item in forbidden if item.casefold() in answer_lower]
    coverage = f"{(len(required) - len(missing)) / len(required):.4f}" if required else ""
    source_match = re.search(r"参考来源[\s\S]*$", answer)
    source_text = source_match.group(0).strip() if source_match else ""
    source_names = re.findall(r"[\w\u4e00-\u9fff.-]+\.(?:txt|md|docx|pdf)", source_text, re.IGNORECASE)
    source_names = list(dict.fromkeys(source_names))
    returned_sources = "||".join(source_names) if source_names else source_text
    expected_sources = split_values(question["expected_sources"])
    returned_set = {name.casefold() for name in source_names}
    source_pass = str(all(item.casefold() in returned_set for item in expected_sources)).lower() if expected_sources and source_names else ""
    should_refuse = question["should_refuse"].strip().lower() == "true"
    refusal_pass = str(not missing and not forbidden_found).lower() if should_refuse else ""
    return coverage, "||".join(missing), "||".join(forbidden_found), returned_sources, source_pass, refusal_pass
def main():
    parser = argparse.ArgumentParser(description="批量运行轻量RAG端到端评测")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端地址")
    parser.add_argument("--username", default="", help="登录用户名，留空时交互输入")
    parser.add_argument("--questions", default="", help="可选题号，例如Q001,Q024,Q038；留空运行全部启用题目")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    username = args.username.strip() or input("用户名：").strip()
    evaluation_dir = Path(__file__).resolve().parent
    question_path, result_path = evaluation_dir / "rag_evaluation_questions.csv", evaluation_dir / "rag_baseline_results.csv"
    try:
        questions = load_questions(question_path, args.questions)
    except (OSError, csv.Error, KeyError, ValueError) as error:
        print(f"评测题目读取失败：{error}")
        return
    if result_path.exists() and input(f"{result_path.name}已存在，是否覆盖？(y/N)：").strip().lower() != "y":
        print("已取消运行")
        return
    password = getpass.getpass("密码：")
    total_runs = sum(int(row["repeat_count"]) for row in questions)
    run_id = str(uuid.uuid4())
    try:
        with httpx.Client(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
            token = login(client, base_url, username, password)
            print(f"登录成功，准备运行{total_runs}条正式结果")
            with result_path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
                writer.writeheader()
                file.flush()
                completed = 0
                for question in questions:
                    for repeat_index in range(1, int(question["repeat_count"]) + 1):
                        completed += 1
                        session_id = str(uuid.uuid4())
                        status, answer, error, total_ms = "", "", "", ""
                        formal_start = None
                        try:
                            if question["setup_question"].strip():
                                status, _, setup_error = send_chat(client, base_url, token, question["setup_question"], session_id)
                                if setup_error:
                                    error = f"setup_question失败：{setup_error}"
                            if not error:
                                formal_start = time.perf_counter()
                                status, answer, error = send_chat(client, base_url, token, question["question"], session_id)
                                total_ms = round((time.perf_counter() - formal_start) * 1000, 2)
                        except httpx.RequestError as request_error:
                            error = f"网络请求失败：{request_error}"
                        except Exception as unexpected_error:
                            error = f"运行异常：{unexpected_error}"
                        if formal_start is not None and total_ms == "": total_ms = round((time.perf_counter() - formal_start) * 1000, 2)
                        coverage, missing, forbidden, sources, source_pass, refusal_pass = analyze_answer(question, answer)
                        result = {field: "" for field in RESULT_FIELDS}
                        result.update({
                            "run_id": run_id, "question_id": question["question_id"], "category": question["category"],
                            "file_format": question["file_format"], "repeat_index": repeat_index, "session_id": session_id,
                            "question": question["question"], "expected_sources": question["expected_sources"],
                            "should_refuse": question["should_refuse"], "http_status": status, "answer": answer,
                            "returned_sources": sources, "required_keyword_coverage": coverage,
                            "missing_required_keywords": missing, "forbidden_keywords_found": forbidden,
                            "source_pass": source_pass, "refusal_pass": refusal_pass, "total_ms": total_ms,
                            "error": error, "tested_at": datetime.now().astimezone().isoformat(timespec="seconds")
                        })
                        writer.writerow(result)
                        file.flush()
                        print(f"[{completed}/{total_runs}] {question['question_id']} 第{repeat_index}次：{'失败' if error else '完成'}")
    except (OSError, httpx.RequestError, RuntimeError, json.JSONDecodeError) as error:
        print(f"评测无法继续：{error}")
        return
    print(f"评测结束，结果已保存到：{result_path}")
if __name__ == "__main__":
    main()
