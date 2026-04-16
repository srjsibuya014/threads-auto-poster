"""
note記事ネタ生成スクリプト
投稿ログを分析して反響の多かったテーマをベースに有料記事の構成案を出力する
"""

import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).parent
LOG_PATH = BASE_DIR / "logs" / "post_log.json"
POSTS_PATH = BASE_DIR / "data" / "posts.json"

# 記事テンプレート（テーマ別）
NOTE_TEMPLATES = {
    "恋愛の型": {
        "title": "【保存版】あなたの「恋愛パターン」を知れば、片思いが終わる",
        "structure": [
            "はじめに：なぜ同じ失敗を繰り返すのか",
            "恋愛の型とは何か（3つの分類）",
            "自分の型を診断する方法",
            "型別：アプローチの変え方",
            "実践：次の一手の選び方",
            "おわりに：自己理解が最強のモテ戦略",
        ],
        "price": 500,
    },
    "LINE術": {
        "title": "好きな人に「この人、違う」と思わせるLINEの送り方",
        "structure": [
            "はじめに：LINEで全部バレる",
            "NGパターン5選と心理",
            "返信を引き出す「余白」の作り方",
            "好意を自然に伝える言葉選び",
            "実例：会話の流れを変えた一文",
        ],
        "price": 300,
    },
    "素直になれない": {
        "title": "好きな人の前でだけ「うまく話せない」理由と処方箋",
        "structure": [
            "はじめに：緊張は本気のサイン",
            "うまく話せなくなるメカニズム",
            "自己開示のハードルを下げる3ステップ",
            "「素の自分」を出して好かれた実例",
            "おわりに：弱さを武器に変える",
        ],
        "price": 300,
    },
}


def load_json(path: Path) -> any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def analyze_logs(log: list) -> dict:
    """投稿ログからタグの出現頻度を集計する"""
    posts = load_json(POSTS_PATH)
    post_map = {p["id"]: p for p in posts}

    tag_counter: Counter = Counter()
    success_count = 0

    for entry in log:
        if entry.get("status") != "success":
            continue
        success_count += 1
        post_id = entry.get("post_id")
        if post_id and post_id in post_map:
            for tag in post_map[post_id].get("tags", []):
                tag_counter[tag] += 1

    return {
        "total_posts": success_count,
        "top_tags": tag_counter.most_common(5),
    }


def suggest_articles(analysis: dict) -> list:
    """分析結果を元に記事候補をサジェストする"""
    suggestions = []
    top_tag_names = [tag for tag, _ in analysis["top_tags"]]

    for theme, template in NOTE_TEMPLATES.items():
        relevance = sum(1 for tag in top_tag_names if theme in tag or tag in theme)
        suggestions.append(
            {
                "theme": theme,
                "title": template["title"],
                "structure": template["structure"],
                "price": template["price"],
                "relevance_score": relevance,
            }
        )

    suggestions.sort(key=lambda x: x["relevance_score"], reverse=True)
    return suggestions


def print_report(analysis: dict, suggestions: list) -> None:
    print("=" * 50)
    print("【noteネタ分析レポート】")
    print("=" * 50)
    print(f"\n投稿成功件数: {analysis['total_posts']}件")
    print("\n頻出タグ TOP5:")
    for tag, count in analysis["top_tags"]:
        print(f"  #{tag}: {count}回")

    print("\n" + "=" * 50)
    print("【記事候補サジェスト】")
    print("=" * 50)
    for i, s in enumerate(suggestions, 1):
        print(f"\n{'─'*40}")
        print(f"候補{i}: {s['theme']}")
        print(f"タイトル案: {s['title']}")
        print(f"想定価格: ¥{s['price']}")
        print("構成案:")
        for j, section in enumerate(s["structure"], 1):
            print(f"  {j}. {section}")


def main():
    log = load_json(LOG_PATH)
    if not log:
        print("投稿ログが空です。投稿が蓄積されてからお試しください。")
        return

    analysis = analyze_logs(log)
    suggestions = suggest_articles(analysis)
    print_report(analysis, suggestions)


if __name__ == "__main__":
    main()
