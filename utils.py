import json
import os
import re
import sqlite3
import time

from requests import RequestException, Session

session = Session()
zenSession = Session()

ZEN_CHAT_URL = "https://opencode.ai/zen/v1/chat/completions"
ZEN_MODEL = "nemotron-3-ultra-free"
ANSWER_LABELS = "ABCDEF"

PROVINCE_ALIASES = {
    "北京": "北京市",
    "天津": "天津市",
    "上海": "上海市",
    "重庆": "重庆市",
    "内蒙古": "内蒙古自治区",
    "广西": "广西壮族自治区",
    "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
    "香港": "香港特别行政区",
    "澳门": "澳门特别行政区",
}


def normalizeProvince(province):
    province = province.strip()
    if not province:
        return "江苏省"
    if province in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[province]
    if province.endswith(("省", "市", "自治区", "特别行政区")):
        return province
    return f"{province}省"


def getAllSchools(province):
    """获取指定省份的学校列表。"""
    raw = session.get(
        "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/select/proCollege",
        params={"provincesName": province},
        timeout=15,
    )
    raw.raise_for_status()
    return raw.json()

def getFacultyBySchoolId(id):
    """通过学校 ID 获取学院列表。"""
    raw = session.post("http://wap.xiaoyuananquantong.com/guns-vip-main/wap/getFaculty",data={"collegeId":id,"notTeacher":10})
    return raw.text

def getClassById(id):
    """通过学院 ID 获取专业列表。"""
    raw = session.post("http://wap.xiaoyuananquantong.com/guns-vip-main/wap/select/class",{"facultyId":id})

def regMethod(name, collegeId, facultyId, classId, account):
    """使用姓名、学校、学院、专业和账号信息注册学生。"""
    raw = session.post("http://wap.xiaoyuananquantong.com/guns-vip-main/wap/jsregisterUser", data={"name":name, "password":"", "collegeId":collegeId, "facultyId":facultyId, "classId":classId, "account":account})
    """
    接口返回示例：
    {
        "code":200,
        "data":{
            "phone":"",
            "auth":"1b7d9a*********************ab20e",
            "success":"\u6CE8\u518C\u6210\u529F",
            "userId":"195**************38"
        },
        "message":"\u8BF7\u6C42\u6210\u529F",
        "success":true
    }
    """

def getUserSchool():
    """根据省份和学校关键词获取登录所需的 collegeId。"""
    while True:
        province = normalizeProvince(input("请输入学校所在省份[回车默认江苏省]："))
        try:
            schoolList = getAllSchools(province)
        except (RequestException, ValueError):
            print("错误：学校列表获取失败，请检查网络后重试")
            continue

        schools = schoolList.get("data", [])
        if not schoolList.get("success") or not schools:
            print(f"未查找到省份“{province}”的学校，请检查省份名称")
            continue
        break

    while True:
        schoolKey = input("请输入学校名称[关键词也可以]：").strip()
        if not schoolKey:
            print("学校名称不能为空，请重新输入")
            continue

        exactMatches = [school for school in schools if school["name"] == schoolKey]
        matches = exactMatches or [school for school in schools if schoolKey in school["name"]]
        if not matches:
            print(f"未在{province}查找到任何学校，请重新输入")
            continue

        if len(matches) == 1:
            school = matches[0]
        else:
            print("查找到以下学校：")
            for index, match in enumerate(matches):
                print(f"[{index}] {match['name']}")

            try:
                index = int(input("请输入数字序号来选择学校："))
                if not 0 <= index < len(matches):
                    raise IndexError
                school = matches[index]
            except (ValueError, IndexError):
                print("您的输入有误，请重新输入学校名称")
                continue

        print(f"已获取学校id：{school['id']}")
        return school["id"]


def loginMethod(username, password, collegeId):
    """
    登录平台并返回用户信息。

    返回样例：
        {
        "code":200,
        "data":{
            "account":"******",
            "area":"",
            "auth":"b12f***********************653ba",
            "avatar":"",
            "birthday":"",
            "classId":"*******************",
            "className":"",
            "collegeId":"*******************",
            "collegeName":"",
            "createTime":"2026-07-28 16:23:26",
            "createUser":"*******************",
            "deptId":"*******************",
            "email":"",
            "facultyId":"*******************",
            "ipAddress":"49.**.***.46",
            "loginNum":3,
            "name":"****",
            "openId":"****************************",
            "password":"",
            "phone":"",
            "roleId":"*******************",
            "salt":"9a5sr",
            "sex":"",
            "status":"ENABLE",
            "sysSource":"20",
            "updateTime":"2026-07-29 09:58:58",
            "updateUser":-100,
            "userId":"*******************",
            "version":""
        },
        "message":"\u8BF7\u6C42\u6210\u529F",
        "success":true
    }
    """
    cookies = {}

    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'Origin': 'http://wap.xiaoyuananquantong.com',
        'Referer': 'http://wap.xiaoyuananquantong.com/guns-vip-main/wap/jiangsuwxJsback',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 16; MEIZU 20 Pro Build/BQ2A.251110.001-BP2A.250605.031.A3; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/146.0.7680.178 Mobile Safari/537.36 XWEB/1460249 MMWEBSDK/20260202 MMWEBID/3950 REV/6666666666666666666666666666666666666666 MicroMessenger/8.0.71.3080(0x28004750) WeChat/arm64 Weixin NetType/5G Language/zh_CN ABI/arm64',
        'X-Requested-With': 'XMLHttpRequest',
    }

    data = {
        'openId': '',
        'account': f'{username}',
        'collegeId': f'{collegeId}',
        'password': f'{password}',
    }

    response = session.post(
        'http://wap.xiaoyuananquantong.com/guns-vip-main/wap/jsUserLogin',
        cookies=cookies,
        headers=headers,
        data=data,
        verify=False,
    )
    return response.json()

def UntyingMethod(userid):
    """解除当前用户的会话绑定。"""
    cookies = {}

    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Referer': 'http://wap.xiaoyuananquantong.com/guns-vip-main/wap/jspersonal',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 16; MEIZU 20 Pro Build/BQ2A.251110.001-BP2A.250605.031.A3; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/146.0.7680.178 Mobile Safari/537.36 XWEB/1460249 MMWEBSDK/20260202 MMWEBID/3950 REV/6666666666666666666666666666666666666666 MicroMessenger/8.0.71.3080(0x28004750) WeChat/arm64 Weixin NetType/5G Language/zh_CN ABI/arm64',
        'X-Requested-With': 'XMLHttpRequest',
    }

    params = {
        'userId': f'{userid}',
    }

    response = session.get(
        'http://wap.xiaoyuananquantong.com/guns-vip-main/wap/JsUntying',
        params=params,
        cookies=cookies,
        headers=headers,
        verify=False,
    )
    return response.json()


def creatExam(examId, userId):
    # 使用平台返回的考试 ID 创建考试。
    response = session.post("http://wap.xiaoyuananquantong.com/guns-vip-main/wap/test/create",data={"examId":examId,"userId":userId})
    return response.json()

def getExam(logId,userId):
    # 获取指定考试记录的题目列表。
    response = session.get("http://wap.xiaoyuananquantong.com/guns-vip-main/wap/test/list?logId=%s&page=1&limit=200&ah=&userId=%s" % (logId,userId))
    return response.json()


def _normalizeQuestionForAi(entry):
    question = entry.get("question", {})
    questionId = str(entry.get("questionId") or question.get("id"))
    quesType = str(entry.get("questType") or question.get("quesType"))
    options = {
        label: str(question.get(f"option{label}", "")).strip()
        for label in ANSWER_LABELS
        if str(question.get(f"option{label}", "")).strip()
    }
    return {
        "questionId": questionId,
        "quesType": quesType,
        "question": str(question.get("question", "")).strip(),
        "options": options,
    }


def _parseZenAnswerContent(content):
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("AI 响应中没有 JSON 对象")
    try:
        parsed = json.loads(content[start:end + 1])
    except json.JSONDecodeError as error:
        raise ValueError("AI 响应不是有效 JSON") from error
    answers = parsed.get("answers", [])
    if not isinstance(answers, list):
        raise ValueError("AI 响应 answers 字段格式错误")
    return answers


def _requestZenAnswers(items):
    prompt = {
        "instructions": [
            "回答中国高校校园安全知识题。",
            "单选题 quesType=1：answers 只能有一个选项字母。",
            "多选题 quesType=2：answers 列出全部正确选项字母。",
            "判断题 quesType=3：正确返回 1，错误返回 0。",
            "只返回 JSON，不要解释。",
        ],
        "outputFormat": {
            "answers": [
                {"questionId": "题目ID", "answers": ["A"]}
            ]
        },
        "questions": items,
    }
    requestBody = {
        "model": ZEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的校园安全知识答题助手，只输出符合要求的 JSON。",
            },
            {
                "role": "user",
                "content": json.dumps(prompt, ensure_ascii=False),
            },
        ],
        "temperature": 0,
    }

    lastError = None
    for attempt in range(3):
        try:
            response = zenSession.post(
                ZEN_CHAT_URL,
                json=requestBody,
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            return _parseZenAnswerContent(content)
        except (RequestException, KeyError, TypeError, ValueError) as error:
            lastError = error
            if attempt < 2:
                time.sleep(attempt + 1)

    raise ValueError("AI 请求连续失败") from lastError


def _validateZenAnswers(rawAnswers, items):
    expected = {item["questionId"]: item for item in items}
    validated = {}
    truthy = {"1", "TRUE", "正确", "对", "是"}
    falsy = {"0", "FALSE", "错误", "错", "否"}

    for result in rawAnswers:
        if not isinstance(result, dict):
            continue
        questionId = str(result.get("questionId", ""))
        item = expected.get(questionId)
        if item is None:
            continue

        raw = result.get("answers", [])
        if not isinstance(raw, list):
            raw = [raw]
        text = ",".join(str(value).strip().upper() for value in raw)

        if item["quesType"] == "3":
            if text in truthy:
                answers = ["1"]
            elif text in falsy:
                answers = ["0"]
            else:
                continue
        else:
            answers = []
            for label in re.findall(r"[A-F]", text):
                if label in item["options"] and label not in answers:
                    answers.append(label)
            if item["quesType"] == "1" and len(answers) != 1:
                continue
            if item["quesType"] == "2" and not answers:
                continue

        validated[questionId] = {
            "questionId": questionId,
            "quesType": item["quesType"],
            "answers": answers,
        }
    return validated


def saveAnswerRecords(records):
    if not records:
        return
    databasePath = os.path.abspath("database.db")
    with sqlite3.connect(databasePath) as conn:
        for record in records:
            questionId = str(record["questionId"])
            quesType = str(record["quesType"])
            conn.execute("DELETE FROM tiku WHERE questionId = ?", (questionId,))
            conn.executemany(
                "INSERT INTO tiku (questionId, answer, quesType) VALUES (?, ?, ?)",
                [
                    (questionId, str(answer), quesType)
                    for answer in record["answers"]
                ],
            )


def answerQuestionsWithAi(questions, batchSize=8):
    items = [_normalizeQuestionForAi(question) for question in questions]
    resolved = {}

    for start in range(0, len(items), batchSize):
        batch = items[start:start + batchSize]
        try:
            rawAnswers = _requestZenAnswers(batch)
        except (RequestException, KeyError, TypeError, ValueError):
            rawAnswers = []
        resolved.update(_validateZenAnswers(rawAnswers, batch))

    unresolved = [item for item in items if item["questionId"] not in resolved]
    for item in unresolved:
        try:
            rawAnswers = _requestZenAnswers([item])
        except (RequestException, KeyError, TypeError, ValueError):
            continue
        resolved.update(_validateZenAnswers(rawAnswers, [item]))

    saveAnswerRecords(list(resolved.values()))
    failed = [
        item["questionId"]
        for item in items
        if item["questionId"] not in resolved
    ]
    return list(resolved), failed


def cacheWrongAnswers(logId, userId):
    response = session.post(
        "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/wrong/list",
        data={"errorLogId": logId, "page": 1, "limit": 200},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise ValueError(payload.get("message", "错题列表获取失败"))

    rows = payload.get("data", {}).get("data", [])
    records = []
    for row in rows:
        question = row.get("question", {})
        questionId = str(row.get("questionId") or question.get("id"))
        quesType = str(question.get("quesType", ""))
        rawAnswer = str(question.get("answer", "")).upper()
        if quesType == "3":
            answers = [rawAnswer] if rawAnswer in {"0", "1"} else []
        else:
            answers = []
            for label in re.findall(r"[A-F]", rawAnswer):
                if label not in answers:
                    answers.append(label)
        if questionId and answers:
            records.append({
                "questionId": questionId,
                "quesType": quesType,
                "answers": answers,
            })

    saveAnswerRecords(records)
    return len(records)


def getAnswerById(id):
    # 从本地数据库读取答案并组装提交参数。
    databasePath = os.path.abspath('database.db')
    with sqlite3.connect(databasePath) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT questionId, answer, quesType
            FROM tiku
            WHERE questionId = ?
            ORDER BY questionId
            """,
            (str(id),),
        )
        records = cursor.fetchall()
    
    # 题库中不存在对应答案。
    if not records:
        return ""
    quesType = records[0][2]
    if quesType == "2":
        # 多选
        question = ""
        for i in records:
            question += "~%s-%s" % (i[0],i[1])
    elif quesType == "1":
        # 单选
        question = "%s-%s" % (records[0][0],records[0][1])
    else:
        # 判断
        question = "%s-%s" % (records[0][0],records[0][1])
    return ("question",question),("questionId",records[0][0]),("quesType",quesType)

def getExamId(userId, examClass=20):
    response = session.post("http://wap.xiaoyuananquantong.com/guns-vip-main/wap/test/getTest",data={"examType":2,"examClass":examClass,"userId":userId,"ah":""})
    return response.json()

def imitateExam(examId,logId,userId,answers):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Referer" : "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/newStudentssimulate?examId=%s&examType=2&userId=%s&ah"% (examId, userId)
        }
    data = [
        ("examId",examId),
        ("examType",2),
        ("sysSource",20),
        ("logId",logId),
        ("userId",userId),
        ("ah",""),
        ]
    data += answers
    result = session.post("http://wap.xiaoyuananquantong.com/guns-vip-main/wap/imitateTest", data=data, headers=headers)
    return result

def end(code: int):
    input()
    raise SystemExit(code)
