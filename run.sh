#!/bin/bash

set -euo pipefail

stage=0
stop_stage=1000
. ./local/parse_options.sh
. ./path.sh

result_dir=results
mkdir -p $result_dir

# Step 1: 產生壓力詞表
if [ $stage -le 1 ] && [ $stop_stage -ge 1 ]; then
    echo "🔹 Step 1: 產生壓力詞表"
    python3 gpt_generate.py \
        --output_path $result_dir/stress_keywords.json \
        --number "100"
fi


if [ $stage -le 2 ] && [ $stop_stage -ge 2 ]; then
    # Step 2: 爬取 PTT & Dcard 貼文
    echo "🔹 Step 2: 爬取 PTT 和 Dcard"
    python3 web_crawler.py \
        --year_limit 1 \
        --max_posts 1000 \
        --keyword_path $result_dir/stress_keywords.json \
        --output_dir $result_dir/collected_posts
fi

if [ $stage -le 3 ] && [ $stop_stage -ge 3 ]; then
    # Step 3: 篩選具壓力文章
    echo "🔹 Step 3: 篩選具壓力文章"
    python3 gpt_select.py \
      --input_csv $results/collected_posts/posts.csv \
      --output_csv $results/filtered_posts.csv
fi
    
if [ $stage -le 4 ] && [ $stop_stage -ge 4 ]; then
    # Step 4: 分析並分類教師壓力來源
    echo "🔹 Step 4: 分析並分類教師壓力來源"
    python3 gpt_summary.py \
        --input_dir $result_dir/collected_posts \
        --keyword_path $result_dir/stress_keywords.json \
        --output_dir $result_dir/analysis_summary
fi
    
echo "✅ 所有步驟完成"
