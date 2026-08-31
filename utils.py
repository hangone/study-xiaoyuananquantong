import random

from requests import RequestException, Session

BASE_URL = "http://wap.xiaoyuananquantong.com/guns-vip-main/wap"
USER_AGENT = "Mozilla/5.0 (Linux; Android 16; Pixel 10 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.7922.108 Mobile Safari/537.36"
ANSWER_LABELS = "ABCDEF"
PROVINCE_ALIASES = {"北京": "北京市", "天津": "天津市", "上海": "上海市", "重庆": "重庆市", "内蒙古": "内蒙古自治区", "广西": "广西壮族自治区", "西藏": "西藏自治区", "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区", "香港": "香港特别行政区", "澳门": "澳门特别行政区"}

session = Session()
session.headers["User-Agent"] = USER_AGENT


def _url(path):
    return f"{BASE_URL}/{path.lstrip('/')}"


def _request(method, path, **kwargs):
    kwargs.setdefault("timeout", 30)
    return session.request(method, _url(path), **kwargs)


def _request_json(method, path, **kwargs):
    response = _request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def _ajax_headers(referer, **headers):
    return {"Accept": "application/json, text/javascript, */*; q=0.01", "Referer": _url(referer), "X-Requested-With": "XMLHttpRequest", **headers}


def normalize_province(province):
    province = province.strip()
    if not province:
        return "江苏省"
    if province in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[province]
    return province if province.endswith(("省", "市", "自治区", "特别行政区")) else f"{province}省"


def get_all_schools(province):
    return _request_json("GET", "select/proCollege", params={"provincesName": province})


def select_school():
    while True:
        province = normalize_province(input("请输入学校所在省份[回车默认江苏省]："))
        try:
            result = get_all_schools(province)
        except (RequestException, ValueError):
            print("学校列表获取失败，请检查网络后重试")
            continue
        schools = result.get("data", [])
        if result.get("success") and schools:
            break
        print(f"未查找到省份“{province}”的学校")

    while True:
        keyword = input("请输入学校名称[关键词也可以]：").strip()
        if not keyword:
            print("学校名称不能为空")
            continue
        exact = [school for school in schools if school["name"] == keyword]
        matches = exact or [school for school in schools if keyword in school["name"]]
        if not matches:
            print(f"未在{province}查找到匹配学校")
            continue
        if len(matches) == 1:
            return matches[0]["id"]
        for index, school in enumerate(matches, 1):
            print(f"[{index}] {school['name']}")
        try:
            selected = int(input("请输入学校序号：")) - 1
            if not 0 <= selected < len(matches):
                raise IndexError
            return matches[selected]["id"]
        except (ValueError, IndexError):
            print("学校序号无效，请重新搜索")


def login(username, password, college_id):
    headers = _ajax_headers("jiangsuwxJsback", Origin="http://wap.xiaoyuananquantong.com", **{"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    data = {"openId": "", "account": username, "collegeId": college_id, "password": password}
    return _request_json("POST", "jsUserLogin", headers=headers, data=data)


def unbind(user_id):
    return _request_json("GET", "JsUntying", headers=_ajax_headers("jspersonal"), params={"userId": user_id})


def get_courses(user_id, college_id):
    return _request_json("POST", "compulsory/list", data={"userId": user_id, "collegeId": college_id})


def get_course_directory(course_id, user_id, college_id):
    return _request_json("POST", "directory/list", data={"courseId": course_id, "userId": user_id, "collegeId": college_id})


def complete_article(article_id, title, user_id):
    data = {"articleId": article_id, "title": title, "userId": user_id, "ah": "", "question": "1677233633049554945-1", "quesType": "3"}
    _request("POST", "unitTest", data=data).raise_for_status()


def get_exam_config(user_id, exam_class):
    data = {"examType": 2, "examClass": exam_class, "userId": user_id, "ah": ""}
    return _request_json("POST", "test/getTest", data=data)


def create_exam(exam_id, user_id):
    return _request_json("POST", "test/create", data={"examId": exam_id, "userId": user_id})


def get_exam_questions(log_id, user_id):
    params = {"logId": log_id, "page": 1, "limit": 200, "ah": "", "userId": user_id}
    return _request_json("GET", "test/list", params=params)


def _question_fields(entry):
    question = entry.get("question", {})
    question_id = str(entry.get("questionId") or question.get("id") or "")
    question_type = str(entry.get("quesType") or entry.get("questType") or question.get("quesType") or "")
    options = [label for label in ANSWER_LABELS if str(question.get(f"option{label}", "")).strip()]
    return question_id, question_type, options


def _random_answer_record(entry):
    question_id, question_type, options = _question_fields(entry)
    if question_type == "1" and options:
        answers = [random.choice(options)]
    elif question_type == "2" and options:
        answers = options
    elif question_type == "3":
        answers = [random.choice(("0", "1"))]
    else:
        raise ValueError(f"题目 {question_id or '未知题目'} 缺少有效题型或选项")
    if not question_id:
        raise ValueError("题目缺少 ID")
    return {"questionId": question_id, "quesType": question_type, "answers": answers}


def build_random_answer_records(questions):
    return [_random_answer_record(question) for question in questions]


def build_exam_answers(records):
    data = []
    for record in records:
        question_id = str(record["questionId"])
        question_type = str(record["quesType"])
        values = [str(value) for value in record["answers"]]
        if question_type == "2" and values:
            answer = "".join(f"~{question_id}-{value}" for value in values)
        elif question_type in {"1", "3"} and len(values) == 1:
            answer = f"{question_id}-{values[0]}"
        else:
            raise ValueError(f"题目 {question_id} 的答案格式无效")
        data.extend((("question", answer), ("questionId", question_id), ("quesType", question_type)))
    return data


def _parse_wrong_answer_records(rows):
    records = []
    for row in rows:
        question = row.get("question", {})
        question_id = str(row.get("questionId") or question.get("id") or "")
        question_type = str(row.get("quesType") or question.get("quesType") or "")
        raw_answer = str(question.get("answer", "")).upper()
        answers = [raw_answer] if question_type == "3" and raw_answer in {"0", "1"} else [label for label in ANSWER_LABELS if question_type in {"1", "2"} and label in raw_answer]
        if question_id and answers:
            records.append({"questionId": question_id, "quesType": question_type, "answers": answers})
    return records


def get_wrong_answer_records(log_id):
    result = _request_json("POST", "wrong/list", data={"errorLogId": log_id, "page": 1, "limit": 200})
    if not result.get("success"):
        raise ValueError(result.get("message", "错题列表获取失败"))
    return _parse_wrong_answer_records(result.get("data", {}).get("data", []))


def merge_answer_records(records, replacements):
    merged = {record["questionId"]: record for record in records}
    merged.update({record["questionId"]: record for record in replacements})
    return list(merged.values())


def submit_exam(exam_id, log_id, user_id, records):
    data = [("examId", exam_id), ("examType", 2), ("sysSource", 20), ("logId", log_id), ("userId", user_id), ("ah", ""), *build_exam_answers(records)]
    referer = _url(f"newStudentssimulate?examId={exam_id}&examType=2&userId={user_id}&ah")
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "Referer": referer}
    result = _request_json("POST", "imitateTest", headers=headers, data=data)
    if not result.get("success"):
        raise ValueError(result.get("message", "考试提交失败"))
    try:
        return int(result["data"]["count"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("考试结果格式无效") from error


def get_certificate(user_id):
    return _request("GET", "qrCode", params={"userId": user_id})
