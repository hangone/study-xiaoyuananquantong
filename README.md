# 校园安全教育平台辅助脚本

用于登录校园安全教育平台、完成课程、提交考试并下载结课证书。

## 环境要求

- Python 3
- `requests>=2.34.2`

## 运行

```bash
uv run main.py
```

或：

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

## 流程

1. 选择省份和学校并登录。
2. 完成未结束的课程。
3. 单选题随机选择，多选题全选，判断题随机选择 `0` 或 `1`。
4. 根据错题反馈校正答案并重新提交。
5. 达到 100 分后下载结课证书。

## 文件

- `main.py`：业务流程。
- `utils.py`：平台接口和答案处理。

## 许可证

GNU Affero General Public License v3.0，详见 `LICENSE`。
