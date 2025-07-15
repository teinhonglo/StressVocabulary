import argparse
import json
import os
import csv
import requests
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin

IGNORED_WORDS = ["教甄", "上榜", "教師甄選", "考題", "新聞"]

def fuzzy_match(text, keywords):
    if not text:
        return []
    matched = [k for k in keywords if k in text]
    return matched

def crawl_ptt(board_url, keywords, max_posts, year_limit):
    print(f"🔍 Crawling PTT board: {board_url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    results = []
    count = 0
    year_ago = datetime.now() - timedelta(days=365 * year_limit)
    next_url = board_url

    while next_url and count < max_posts:
        res = requests.get(next_url, headers=headers, cookies={"over18": "1"})
        soup = BeautifulSoup(res.text, "html.parser")
        entries = soup.select("div.r-ent")

        for entry in entries:
            title_tag = entry.select_one("div.title > a")
            if not title_tag:
                continue

            title = title_tag.text.strip()
            if title.startswith("Re:"):
                continue
            ignored_words = [k in title for k in IGNORED_WORDS if k in title]
            if len(ignored_words) > 0:
                continue

            date_str = entry.select_one(".date").text.strip()
            try:
                post_date = datetime.strptime(date_str, "%m/%d").replace(year=datetime.now().year)
                if post_date > datetime.now():
                    post_date = post_date.replace(year=datetime.now().year - 1)
            except:
                continue

            if post_date < year_ago:
                continue

            href = urljoin("https://www.ptt.cc", title_tag["href"])
            art_res = requests.get(href, headers=headers, cookies={"over18": "1"})
            art_soup = BeautifulSoup(art_res.text, "html.parser")
            main_content = art_soup.select_one("#main-content")
            if main_content:
                for tag in main_content.select("div.push, span.article-meta-tag, div.article-metaline, div.article-metaline-right"):
                    tag.decompose()
                content = main_content.get_text().strip()
            else:
                content = ""
            content = "".join(content.split())
            matched_keywords = fuzzy_match(content, keywords)            

            if len(matched_keywords) > 0:
                results.append({
                    "source": board_url,
                    "date": post_date.strftime("%Y-%m-%d"),
                    "url": href,
                    "title": title,
                    "content": content,
                    "matched_keywords": " ".join(matched_keywords)
                })
                count += 1
                print(f"✅ matched: {title}, matched_keywords: {matched_keywords}")

            if count >= max_posts:
                break

        prev = soup.select_one("a:contains('上頁')")
        if prev:
            try:
                next_url = urljoin("https://www.ptt.cc", prev["href"])
                time.sleep(0.5)
            except:
                break
        else:
            break

    return results

def crawl_dcard(keywords, max_posts, year_limit):
    print(f"🔍 Crawling Dcard 教師板（API）")
    base_url = "https://www.dcard.tw/service/api/v2/forums/teacher/posts"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.dcard.tw/f/teacher"
    }
    results = []
    count = 0
    before = int(time.time() * 1000)
    year_ago = datetime.now() - timedelta(days=365 * year_limit)

    while count < max_posts:
        try:
            params = {"limit": 30, "before": before}
            res = requests.get(base_url, headers=headers, params=params, timeout=10)
            posts = res.json()
        except Exception:
            print("❌ Dcard API 無法解析，停止爬取")
            break

        if not posts:
            break

        for post in posts:
            try:
                created = datetime.fromisoformat(post["createdAt"][:-1])
                if created < year_ago:
                    continue

                post_id = post["id"]
                detail_url = f"https://www.dcard.tw/service/api/v2/posts/{post_id}"
                detail_res = requests.get(detail_url, headers=headers, timeout=10)
                detail = detail_res.json()

                title = detail.get("title", "")
                
                ignored_words = [k in title for k in IGNORED_WORDS if k in title]
                if len(ignored_words) > 0:
                    continue
                
                content = detail.get("content", "").strip().replace("\n", "")
                if not content:
                    continue
                
                matched_keywords = fuzzy_match(content, keywords)
                if len(matched_keywords) > 0:
                    results.append({
                        "source": "dcard",
                        "date": created.strftime("%Y-%m-%d"),
                        "url": f"https://www.dcard.tw/f/teacher/p/{post_id}",
                        "title": title,
                        "content": content,
                        "matched_keywords": " ".join(matched_keywords)
                    })
                    count += 1
                    print(f"✅ matched: {title}, matched_keywords: {matched_keywords}")

                if count >= max_posts:
                    break
                time.sleep(0.3)
            except Exception as e:
                print(f"⚠️ 跳過錯誤貼文：{post.get('id')}")
                continue

        before = posts[-1]["createdAt"]

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--year_limit", type=float, default=1.0)
    parser.add_argument("--max_posts", type=int, default=100)
    args = parser.parse_args()

    with open(args.keyword_path, encoding="utf-8") as f:
        data = json.load(f)
    keywords = data["keywords"]

    os.makedirs(args.output_dir, exist_ok=True)
    all_posts = []

    ptt_posts = crawl_ptt("https://www.ptt.cc/bbs/studyteacher/index.html", keywords, args.max_posts, args.year_limit)
    ptt_posts2 = crawl_ptt("https://www.ptt.cc/bbs/Teacher/index.html", keywords, args.max_posts, args.year_limit)
    dcard_posts = crawl_dcard(keywords, args.max_posts, args.year_limit)
    
    for post in [ptt_posts, ptt_posts2, dcard_posts]:
        if len(post) > 0:
            all_posts += post
    

    out_csv = os.path.join(args.output_dir, "posts.csv")
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "date", "url", "title", "content", "matched_keywords"])
        writer.writeheader()
        writer.writerows(all_posts)

    print(f"\n✅ 爬文完成，共儲存 {len(all_posts)} 篇文章至 {out_csv}")

