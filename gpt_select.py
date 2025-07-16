import argparse
import csv
import json
import os
from openai import OpenAI
from tqdm import tqdm

client = OpenAI()

def ask_gpt_is_stress(content):
    system_msg = "你是一位專業語言心理分析師。"
    user_msg = (
        "以下是一篇來自 PTT 或 Dcard 的教師論壇貼文。\n"
        "請你判斷這篇貼文的語氣是否呈現出『情緒壓力』，例如：疲憊、崩潰、煩躁、無力、等情緒？\n"
        "如果有這類情緒，請回覆：是。\n"
        "如果只是中性、討論教學方法、或偏正向，請回覆：否。\n\n"
        f"貼文內容：\n{content[:1000]}"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        temperature=0
    )

    answer = response.choices[0].message.content.strip()
    return answer == "是"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv", required=True)
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()

    with open(args.input_csv, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    neg_selected = []
    pos_selected = []
    positive, negative = 0, 0

    for row in tqdm(reader, desc="🔍 GPT篩選中"):
        content = row["content"]
        try:
            if ask_gpt_is_stress(content):
                neg_selected.append(row)
                negative += 1
            else:
                pos_selected.append(row)
                positive += 1
        except Exception as e:
            print(f"⚠️ GPT 分析失敗，略過一篇文章：{row['url']}")
            continue

    output_neg_csv = os.path.join(args.output_dir, "neg.csv")
    with open(output_neg_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=reader[0].keys())
        writer.writeheader()
        writer.writerows(neg_selected)
    
    output_pos_csv = os.path.join(args.output_dir, "pos.csv")
    with open(output_pos_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=reader[0].keys())
        writer.writeheader()
        writer.writerows(pos_selected)
    
    print(f"\n✅ 篩選完成：共 {len(reader)} 篇 → 保留 {positive} 篇有壓力，排除 {negative} 篇無壓力")

