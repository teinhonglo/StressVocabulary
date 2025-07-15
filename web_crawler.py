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

def save_matched_post(post_dict, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, "posts.csv")
    is_new = not os.path.exists(save_path)

    with open(save_path, "a", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["source", "date", "url", "title", "content", "matched_keywords"])
        if is_new:
            writer.writeheader()
        writer.writerow(post_dict)

def safe_request(url, headers=None, cookies=None, max_retries=3, sleep_time=2, timeout=10):
    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=headers, cookies=cookies, timeout=timeout)
            res.raise_for_status()
            return res
        except Exception as e:
            print(f"⚠️ Request failed: {url} (第 {attempt+1} 次嘗試)，原因：{e}")
            time.sleep(sleep_time)
    time.sleep(sleep_time)
    print(f"❌ 放棄該網址：{url}")
    return None

def load_visited_urls(output_dir):
    visited = set()
    csv_path = os.path.join(output_dir, "posts.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                visited.add(row["url"])
    return visited

def fuzzy_match(text, keywords):
    if not text:
        return []
    matched = [k for k in keywords if k in text]
    return matched

def crawl_ptt(board_url, keywords, max_posts, year_limit, visited_url):
    print(f"🔍 Crawling PTT board: {board_url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.ptt.cc/",
        "Cookie": "over18=1"
    }
    
    results = []
    count = 0
    year_ago = datetime.now() - timedelta(days=365 * year_limit)
    next_url = board_url

    while next_url and count < max_posts:
        res = safe_request(next_url, headers=headers, cookies={"over18": "1"})
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
            
            if href in visited_url:
                count += 1
                continue
            
            art_res = safe_request(href, headers=headers, cookies={"over18": "1"})
            
            if art_res is None:
                continue
            
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
                matched_post ={
                    "source": board_url,
                    "date": post_date.strftime("%Y-%m-%d"),
                    "url": href,
                    "title": title,
                    "content": content,
                    "matched_keywords": " ".join(matched_keywords)
                }
                count += 1
                save_matched_post(matched_post, args.output_dir)
                results.append(matched_post)
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

def crawl_dcard(keywords, max_posts, year_limit, visited_url):
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
            res = safe_request(base_url, headers=headers, params=params, timeout=10)
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
                if detail_url in visited_url:
                    continue
                
                detail_res = safe_request(detail_url, headers=headers, timeout=10)
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
                    matched_post = {
                        "source": "dcard",
                        "date": created.strftime("%Y-%m-%d"),
                        "url": f"https://www.dcard.tw/f/teacher/p/{post_id}",
                        "title": title,
                        "content": content,
                        "matched_keywords": " ".join(matched_keywords)
                    }
                    count += 1
                    save_matched_post(matched_post, args.output_dir)
                    results.append(matched_post)
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
    visited_urls = load_visited_urls(args.output_dir)
    
    ptt_posts = crawl_ptt("https://www.ptt.cc/bbs/studyteacher/index.html", keywords, args.max_posts, args.year_limit, visited_urls)
    ptt_posts2 = crawl_ptt("https://www.ptt.cc/bbs/Teacher/index.html", keywords, args.max_posts, args.year_limit, visited_urls)
    dcard_posts = crawl_dcard(keywords, args.max_posts, args.year_limit, visited_urls)
    
    for post in [ptt_posts, ptt_posts2, dcard_posts]:
        if len(post) > 0:
            all_posts += post
    
    out_csv = os.path.join(args.output_dir, "posts.csv")
    print(f"\n✅ 爬文完成，原始文章{len(visited_urls)}，共新增儲存 {len(all_posts)} 篇文章至 {out_csv}")
