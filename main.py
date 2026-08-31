import base64
import re
import sys
from pathlib import Path

from requests import RequestException

import utils

CERTIFICATE_PATTERN = re.compile(r"data:image/(\w+);base64,([A-Za-z0-9+/=]+)")
CERTIFICATE_EXTENSIONS = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "webp": "webp"}


def require_data(result, action):
    if not isinstance(result, dict) or not result.get("success"):
        message = result.get("message", "未知错误") if isinstance(result, dict) else "响应格式无效"
        raise RuntimeError(f"{action}失败：{message}")
    if result.get("data") is None:
        raise RuntimeError(f"{action}失败：平台未返回数据")
    return result["data"]


def load_courses(user_id, college_id, action="获取课程列表"):
    courses = require_data(utils.get_courses(user_id, college_id), action)
    if not isinstance(courses, list):
        raise TypeError(f"{action}失败：课程数据格式无效")
    return courses


def show_courses(courses):
    print("课程进度：")
    for index, course in enumerate(courses, 1):
        print(f"{index}. {course.get('name', '未命名课程')}：{'已完成' if course.get('isFinsh') else '未完成'}")


def complete_courses(user_id, college_id):
    courses = load_courses(user_id, college_id)
    show_courses(courses)
    unfinished = [course for course in courses if not course.get("isFinsh")]
    if not unfinished:
        return
    for course in unfinished:
        name = course.get("name", "未命名课程")
        directory = utils.get_course_directory(course.get("id"), user_id, college_id)
        if not directory.get("success"):
            print(f"课程目录获取失败：{name}")
            continue
        for chapter in directory.get("data", []):
            if chapter.get("isFinsh"):
                continue
            for article in chapter.get("list", []):
                article_id = article.get("id")
                if article_id:
                    title = article.get("course") or article.get("name") or name
                    print(f"正在完成：{name} / {title}")
                    utils.complete_article(article_id, title, user_id)
    courses = load_courses(user_id, college_id, "刷新课程进度")
    show_courses(courses)
    unfinished = [course.get("name", "未命名课程") for course in courses if not course.get("isFinsh")]
    if unfinished:
        raise RuntimeError("课程仍未完成：" + "、".join(unfinished))


def find_exam(user_id):
    for exam_class in (20, 10):
        result = utils.get_exam_config(user_id, exam_class)
        if result.get("success") and result.get("data"):
            return result["data"]
    raise RuntimeError("未找到可用考试，请确认课程已完成或考试已开放")


def take_exam(user_id):
    print("正在准备考试...")
    exam = find_exam(user_id)
    created = require_data(utils.create_exam(exam["id"], user_id), "创建考试")
    log_id = created.get("logId")
    if not log_id:
        raise RuntimeError("创建考试失败：平台未返回考试记录")
    exam_data = require_data(utils.get_exam_questions(log_id, user_id), "获取考题")
    questions = exam_data.get("data", []) if isinstance(exam_data, dict) else []
    if not questions:
        raise RuntimeError("获取考题失败：题目列表为空")
    records = utils.build_random_answer_records(questions)
    print(f"正在提交 {len(records)} 道题...")
    score = utils.submit_exam(exam["id"], log_id, user_id, records)
    print(f"首次得分：{score}")
    if score == 100:
        return score
    try:
        corrections = utils.get_wrong_answer_records(log_id)
    except (RequestException, KeyError, TypeError, ValueError) as error:
        print(f"错题校正失败：{error}")
        return score
    if corrections:
        print(f"正在校正 {len(corrections)} 道错题并重新提交...")
        score = utils.submit_exam(exam["id"], log_id, user_id, utils.merge_answer_records(records, corrections))
        print(f"校正后得分：{score}")
    return score


def download_certificate(user_id):
    response = utils.get_certificate(user_id)
    if not response.ok:
        try:
            message = response.json().get("message", f"HTTP {response.status_code}")
        except (AttributeError, TypeError, ValueError):
            message = f"HTTP {response.status_code}"
        raise RuntimeError(f"证书获取失败：{message}")
    match = CERTIFICATE_PATTERN.search(response.text)
    if not match:
        raise RuntimeError("证书页面中没有可下载的图片")
    extension = CERTIFICATE_EXTENSIONS.get(match.group(1).lower())
    if not extension:
        raise RuntimeError(f"不支持的证书图片格式：{match.group(1)}")
    directory = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    target = directory / f"certificate.{extension}"
    target.write_bytes(base64.b64decode(match.group(2), validate=True))
    print(f"证书已保存：{target}")


def unbind(user_id):
    try:
        result = utils.unbind(user_id)
        if not result.get("success"):
            print(f"退出登录失败：{result.get('message', '未知错误')}")
    except (RequestException, ValueError) as error:
        print(f"退出登录失败：{error}")


def run():
    college_id = utils.select_school()
    result = utils.login(input("请输入账号：").strip(), input("请输入密码：").strip(), college_id)
    user_id = require_data(result, "登录").get("userId")
    if not user_id:
        raise RuntimeError("登录失败：平台未返回用户 ID")
    try:
        complete_courses(user_id, college_id)
        score = take_exam(user_id)
        if score != 100:
            print("考试未达到 100 分，请检查平台错题反馈或题目配置")
            return 1
        download_certificate(user_id)
        return 0
    finally:
        unbind(user_id)


def main():
    try:
        return run()
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except (RequestException, RuntimeError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"执行失败：{error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
