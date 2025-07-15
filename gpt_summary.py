import argparse
import csv
import json
import os
from collections import Counter
from openai import OpenAI

client = OpenAI()

def classify_stress_source(content, keywords):
    prompt = f"""你是一位教育研究員。以下是一篇教師論壇文章，請幫我判斷其主要壓力來源是哪一類，並只從以下類別中選出最相關的壓力源：
1. 學生問題
2. 家長互動
3. 行政繁瑣
4. 教學負擔
5. 導師責任
6. 校園人際

請僅回覆分類標籤，例如：教學負擔。

文章如下：
---
{content[:1000]}"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "你是一位熟悉教師工作的教育研究員。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--keyword_path", required=True)
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    with open(args.keyword_path, encoding="utf-8") as f:
        keywords = json.load(f)["keywords"]

    input_csv = os.path.join(args.input_dir, "posts.csv")
    classified = []
    stats = Counter()

    with open(input_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            content = row["content"]
            if any(k in content for k in keywords):
                category = classify_stress_source(content, keywords)
                stats[category] += 1
                row["stress_category"] = category
                classified.append(row)

    with open(os.path.join(args.output_dir, "classified_posts.csv"), "w", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=classified[0].keys())
        writer.writeheader()
        writer.writerows(classified)

    with open(os.path.join(args.output_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

