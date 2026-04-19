"""
Threads 自動投稿スクリプト
GitHub Actions から呼び出され、時刻・曜日に応じた投稿タイプを選択して投稿する
"""

import json
import os
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

from checker import run_all_checks

# ---- パス定義 ----
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
POSTS_PATH = BASE_DIR / "data" / "posts.json"
LOG_PATH = BASE_DIR / "logs" / "post_log.json"

# ---- JST ----
JST = timezone(timedelta(hours=9))


def load_json(path: Path) -> any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def determine_post_type(now: datetime, config: dict) -> str:
    """
    現在時刻・曜日から投稿タイプを決定する
    - 朝スロット  → 共感型
    - 夜スロット（金曜）→ 誘導型
    - 夜スロット（平日）→ 共感型70% / 気づき型30%
    """
    hour = now.hour
    weekday = now.weekday()  # 0=月, 4=金

    morning_start = config["post_schedule"]["morning"]["hour_start"]
    morning_end = config["post_schedule"]["morning"]["hour_end"]
    evening_start = config["post_schedule"]["evening"]["hour_start"]
    evening_end = config["post_schedule"]["evening"]["hour_end"]

    if morning_start <= hour < morning_end:
        return "共感型"

    if evening_start <= hour < evening_end:
        if weekday == 4:  # 金曜
            return "誘導型"
        ratio = config["evening_type_ratio"]
        return random.choices(
            ["共感型", "気づき型"],
            weights=[ratio["共感型"], ratio["気づき型"]],
        )[0]

    # スケジュール外（GitHub Actions の設定ミス等）
    raise RuntimeError(f"投稿スロット外の時刻です: {now.strftime('%H:%M')} JST")


def select_post(posts: list, post_type: str) -> dict | None:
    """未使用の投稿から指定タイプをランダムに選ぶ"""
    candidates = [p for p in posts if p["type"] == post_type and not p["used"]]
    if not candidates:
        return None
    return random.choice(candidates)


def build_content(post: dict, config: dict) -> str:
    """誘導型の場合に {note_url} を実際の URL に置換する"""
    return post["threads"].replace("{note_url}", config["note_url"])


def post_to_threads(content: str, config: dict) -> dict:
    """
    Threads Graph API でテキスト投稿する
    必要な環境変数: THREADS_ACCESS_TOKEN
    """
    access_token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not access_token:
        raise EnvironmentError("環境変数 THREADS_ACCESS_TOKEN が設定されていません")

    user_id = config["threads_user_id"]
    base_url = f"https://graph.threads.net/v1.0/{user_id}"

    # Step 1: メディアコンテナ作成
    create_resp = requests.post(
        f"{base_url}/threads",
        params={
            "media_type": "TEXT",
            "text": content,
            "access_token": access_token,
        },
        timeout=30,
    )
    create_resp.raise_for_status()
    container_id = create_resp.json()["id"]

    # Step 2: 公開
    publish_resp = requests.post(
        f"{base_url}/threads_publish",
        params={
            "creation_id": container_id,
            "access_token": access_token,
        },
        timeout=30,
    )
    publish_resp.raise_for_status()
    return publish_resp.json()


def write_log(log: list, entry: dict) -> None:
    log.append(entry)
    save_json(LOG_PATH, log)


def main():
    now = datetime.now(JST)
    print(f"[{now.isoformat()}] 投稿処理開始")

    config = load_json(CONFIG_PATH)
    posts = load_json(POSTS_PATH)
    log = load_json(LOG_PATH)

    post_type = determine_post_type(now, config)
    print(f"投稿タイプ: {post_type}")

    max_retries = config["quality_check"]["max_retries"]
    selected = None
    errors_summary = []

    for attempt in range(1, max_retries + 1):
        candidate = select_post(posts, post_type)
        if candidate is None:
            print(f"[警告] タイプ '{post_type}' の未使用投稿がありません")
            sys.exit(1)

        passed, errors = run_all_checks(candidate, config)
        if passed:
            selected = candidate
            print(f"品質チェック合格（{attempt}回目）: {candidate['id']}")
            break

        print(f"品質チェック失敗（{attempt}回目）: {errors}")
        errors_summary.extend(errors)

        # 失敗した投稿を一時的に除外して再抽選できるよう used フラグは変えない

    if selected is None:
        entry = {
            "timestamp": now.isoformat(),
            "status": "failed",
            "post_type": post_type,
            "reason": f"品質チェック {max_retries} 回失敗",
            "errors": errors_summary,
        }
        write_log(log, entry)
        print("投稿失敗: 品質チェックを通過する投稿が見つかりませんでした")
        sys.exit(1)

    content = build_content(selected, config)

    try:
        result = post_to_threads(content, config)
        thread_id = result.get("id", "unknown")
        print(f"投稿成功: thread_id={thread_id}")

        # used フラグを更新
        for p in posts:
            if p["id"] == selected["id"]:
                p["used"] = True
                p["used_at"] = now.isoformat()
        save_json(POSTS_PATH, posts)

        entry = {
            "timestamp": now.isoformat(),
            "status": "success",
            "post_id": selected["id"],
            "post_type": post_type,
            "thread_id": thread_id,
            "content_preview": content[:50] + "…",
        }
    except Exception as e:
        print(f"投稿エラー: {e}")
        entry = {
            "timestamp": now.isoformat(),
            "status": "error",
            "post_id": selected["id"],
            "post_type": post_type,
            "error": str(e),
        }
        write_log(log, entry)
        sys.exit(1)

    write_log(log, entry)
    print("処理完了")


if __name__ == "__main__":
    main()
