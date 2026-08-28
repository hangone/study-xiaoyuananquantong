import base64
from getpass import getpass
import os
import re
import sys
import time
from typing import NoReturn

from requests import RequestException

import utils

# 校园安全教育平台课程与考试自动化脚本（登录版）

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print("切换到工作目录：", os.getcwd())
# 固定工作目录，确保本地题库始终从脚本目录读取。
print("运行模式：登录版")
session = utils.session  # 统一使用 Session 以保留登录 Cookie。
collegeId = utils.getUserSchool()
username = str(input("请输入账号：").strip())
password = getpass("请输入密码：").strip()

loginResult = utils.loginMethod(username, password, collegeId)
if not loginResult['success']:
    print("登录失败，请检查账号密码和学校是否正确")
    print(loginResult.get("message", "平台未返回错误详情"))
    utils.end(1)
userId = loginResult['data']['userId']


def unbindSession():
    print("正在解绑会话并退出登录...")
    try:
        result = utils.UntyingMethod(userId)
        print(result)
    except Exception as error:
        print(f"会话解绑失败：{error}")


def endSession(code: int) -> NoReturn:
    unbindSession()
    utils.end(code)
    raise SystemExit(code)


def collectExamAnswers(questions):
    answers = ()
    missingQuestions = []
    for question in questions:
        answer = utils.getAnswerById(question["questionId"])
        if answer:
            answers += answer
        else:
            missingQuestions.append(question)
    return answers, missingQuestions


def submitExamAnswers(examId, logId, answers):
    response = utils.imitateExam(examId, logId, userId, answers)
    try:
        result = response.json()
        if not result.get("success"):
            raise ValueError(result.get("message", "考试提交失败"))
        return int(result["data"]["count"])
    except (AttributeError, KeyError, TypeError, ValueError):
        print("考试结果解析失败")
        endSession(1)


print(f"获取到了userId {userId}，开始执行脚本")
start_time = time.time()
learningQuestion = {
    "question": "1677233633049554945-1",
    "quesType": "3",
}

courseResult = session.post(
    "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/compulsory/list",
    data={"userId": userId, "collegeId": collegeId},
).json()
if not courseResult.get("success"):
    print("课程列表获取失败：", courseResult.get("message", "未知错误"))
    endSession(1)

courses = courseResult["data"]
unfinishedCourses = [course for course in courses if not course["isFinsh"]]
print("正在遍历课程列表，查询完成度：")
for index, course in enumerate(courses, start=1):
    status = "已完成" if course["isFinsh"] else "未完成"
    print(f"第{index}课 {course['name']} {status}")

if not unfinishedCourses:
    print("检测到所有课程已经完成，直接进入考试")
else:
    for course in unfinishedCourses:
        directoryResult = session.post(
            "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/directory/list",
            data={"courseId": course["id"], "userId": userId, "collegeId": collegeId},
        ).json()
        if not directoryResult.get("success"):
            print(f"课程目录获取失败：{course['name']}")
            continue

        for chapter in directoryResult.get("data", []):
            if chapter.get("isFinsh"):
                continue
            for article in chapter.get("list", []):
                articleId = article.get("id")
                title = article.get("course") or article.get("name") or course["name"]
                if not articleId:
                    continue
                print(f"正在完成 {course['name']} / {title}")
                session.post(
                    "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/unitTest",
                    data={
                        "articleId": articleId,
                        "title": title,
                        "userId": userId,
                        "ah": "",
                        **learningQuestion,
                    },
                )

    print("课程完成度查询(完成后)：")
    courseResult = session.post(
        "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/compulsory/list",
        data={"userId": userId, "collegeId": collegeId},
    ).json()
    if not courseResult.get("success"):
        print("课程完成度刷新失败：", courseResult.get("message", "未知错误"))
        endSession(1)
    courses = courseResult.get("data", [])
    unfinishedCourses = [course for course in courses if not course["isFinsh"]]
    for index, course in enumerate(courses, start=1):
        status = "已完成" if course["isFinsh"] else "未完成"
        print(f"第{index}课 {course['name']} {status}")

    if unfinishedCourses:
        names = "、".join(course["name"] for course in unfinishedCourses)
        print(f"以下课程仍未完成：{names}")
        print("程序不会在课程未完成时继续创建考试")
        endSession(1)
    print("已完成课程学习")

print("正在进入考试流程...")
examData = None
for examClass in (20, 10):
    result = utils.getExamId(userId, examClass=examClass)
    if result.get("success") and result.get("data"):
        examData = result["data"]
        print(f"已匹配 examClass {examClass}")
        break
    print(f"examClass {examClass} 暂无可用考试，尝试下一类型")

if examData is None:
    print("获取考试ID失败，请确认课程已完成或平台考试已开放")
    endSession(1)

examId = examData["id"]
createResult = utils.creatExam(examId, userId)
if not createResult.get("success") or not createResult.get("data"):
    print("创建考试失败：", createResult.get("message", "未知错误"))
    endSession(1)
logId = createResult["data"]["logId"]
print("取得logId %s" % logId)
examList = utils.getExam(logId=logId, userId=userId)
questions = examList.get("data", {}).get("data", [])
if not questions:
    print("未取得考题列表")
    endSession(1)

print("取得考题列表，正在从数据库中读取答案然后整合...")
answers, missingQuestions = collectExamAnswers(questions)
if missingQuestions:
    print(f"本地题库缺少 {len(missingQuestions)} 道题，正在调用 {utils.ZEN_MODEL} 补全答案...")
    answered, failed = utils.answerQuestionsWithAi(missingQuestions)
    print(f"AI 已缓存 {len(answered)} 道题的答案")
    if failed:
        print("以下题目未能取得有效 AI 答案：" + "、".join(failed))
        endSession(1)
    answers, missingQuestions = collectExamAnswers(questions)
    if missingQuestions:
        print("AI 答案写入后仍有题目缺失")
        endSession(1)

print("答案已生成，正在提交考试...")
score = submitExamAnswers(examId, logId, answers)
print(f"得分：{score}")
if score != 100:
    try:
        corrected = utils.cacheWrongAnswers(logId, userId)
    except (RequestException, KeyError, TypeError, ValueError) as error:
        print(f"错题答案校正失败：{error}")
        corrected = 0

    if corrected:
        print(f"已根据平台错题反馈校正 {corrected} 道题，正在重新提交...")
        answers, missingQuestions = collectExamAnswers(questions)
        if missingQuestions:
            print("校正后题库仍不完整")
            endSession(1)
        score = submitExamAnswers(examId, logId, answers)
        print(f"校正后得分：{score}")

if score != 100:
    print("未达到100分，请检查题库或平台题目配置是否更新。")
else:
    print("正在获取结课证书...")
    cer = session.get(f"http://wap.xiaoyuananquantong.com/guns-vip-main/wap/qrCode?userId={userId}")
    if not cer.ok:
        try:
            certificateError = cer.json().get("message", f"HTTP {cer.status_code}")
        except (AttributeError, TypeError, ValueError):
            certificateError = f"HTTP {cer.status_code}"
        print(f"证书获取失败：{certificateError}")
    else:
        r = re.search(r'data:image/(\w+);base64,([A-Za-z0-9+/=]+)', cer.text)
        if r:
            imageType = r.group(1).lower()
            imageExtensions = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "webp": "webp"}
            imageExtension = imageExtensions.get(imageType)
            if imageExtension is None:
                print(f"证书图片格式不受支持：{imageType}")
                unbindSession()
                raise SystemExit(1)

            # 打包运行时保存到可执行文件所在目录。
            save_dir = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else script_dir
            name = os.path.join(save_dir, f"certificate.{imageExtension}")
            try:
                with open(name, "wb") as f:
                    f.write(base64.b64decode(r.group(2)))
                print(f"证书图片已下载到本地：{name}")
            except (OSError, ValueError):
                print("证书图片写入失败！")
        else:
            print("证书页面中没有可下载的图片")
unbindSession()
end_time = time.time()
elapsed_ms = (end_time - start_time) * 1000
print(f"execute time: {elapsed_ms:.3f} ms.")
input("程序结束，按回车键退出。")
