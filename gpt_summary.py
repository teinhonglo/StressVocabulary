import argparse
import csv
import json
import os
from collections import Counter
from openai import OpenAI
import re

client = OpenAI()

# 函數：分類壓力源
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

# 函數：過濾無關文章，檢查標題與內容是否包含關鍵字
def filter_unwanted_posts(content, keywords):
    if len(content.split()) < 20:  # 過濾掉字數過少的文章
        return True
    
    # 檢查是否包含任何關鍵字
    if not any(k in content for k in keywords):
        return True

    return False

# 函數：命中關鍵詞並提取包含關鍵詞的句子
def find_matched_keywords(content, keywords):
    matched_keywords = []
    sentences = re.split(r'(?<=[.!?]) +', content)  # 根據標點符號分割句子
    
    matched_sentences = []
    for sentence in sentences:
        for keyword in keywords:
            if keyword in sentence and keyword not in matched_keywords:
                matched_keywords.append(keyword)
                matched_sentences.append(sentence.strip())
    return matched_keywords, matched_sentences

# 主要執行流程
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

    # 讀取CSV並分類
    with open(input_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            content = row["content"]

            # 過濾無關文章
            if filter_unwanted_posts(content, keywords):
                continue
            
            # 查找命中的關鍵詞與句子
            matched_keywords, matched_sentences = find_matched_keywords(content, keywords)
            if not matched_keywords:
                continue  # 若沒有命中關鍵詞則跳過

            # 根據內容分類壓力源
            category = classify_stress_source(content, keywords)
            stats[category] += 1

            row["stress_category"] = category
            row["matched_keywords"] = ", ".join(matched_keywords)  # 保存命中的關鍵詞
            row["matched_sentences"] = " | ".join(matched_sentences)  # 保存命中的句子
            classified.append(row)

    # 儲存已分類的文章結果
    with open(os.path.join(args.output_dir, "classified_posts.csv"), "w", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=classified[0].keys())
        writer.writeheader()
        writer.writerows(classified)

    # 儲存統計結果
    with open(os.path.join(args.output_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"分類完成，結果已儲存到 {args.output_dir}")
