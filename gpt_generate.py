import argparse
import json
from openai import OpenAI

client = OpenAI()

def generate_stress_keywords(number):
    system_prompt = (
        f"請列出{number}個中文常見用來描述壓力、煩悶、情緒低落的詞語或短語，"
        "例如：好想哭、壓力大、快崩潰。請直接輸出 JSON list 格式，"
        "不要加上任何說明或其他句子。"
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "請開始產生詞彙"}
        ]
    )
    content = response.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        with open("gpt_raw_output.txt", "w", encoding="utf-8") as f:
            f.write(content)
        print("❌ 回傳不是 JSON 格式，內容已存至 gpt_raw_output.txt")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_path", required=True)
    parser.add_argument("--number", required=True)
    args = parser.parse_args()

    keywords = generate_stress_keywords(number=args.number)
    with open(args.output_path, "w", encoding="utf-8") as f:
        json.dump({"keywords": keywords}, f, ensure_ascii=False, indent=2)

