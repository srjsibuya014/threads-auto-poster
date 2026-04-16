"""
品質チェッカー
投稿前に禁止ワード・口調・文字数・noteリンクを検証する
"""

import re
from typing import Tuple

# 禁止ワード（誘導臭・宣伝臭が強い表現）
FORBIDDEN_WORDS = [
    "続きはnoteで",
    "続きはnoteに",
    "ぜひ読んで",
    "ぜひご覧",
    "プロフから",
    "プロフィールから",
    "リンクから",
    "フォローして",
    "保存して",
    "シェアして",
    "拡散して",
    "読んでみて",
]

# 上から目線・説教口調パターン
PREACHY_PATTERNS = [
    r"すべき(だ|です|でしょう)",
    r"しなければ(いけない|ならない)",
    r"〜すること(が|は)大切",
    r"わかってない",
    r"甘い(考え|んです)",
    r"正直言って",
    r"はっきり言(う|います)",
    r"あなたに(は|も)(わかって|理解して)",
    r"当たり前(のこと|でしょう)",
]

NOTE_URL_PATTERN = re.compile(r"https?://note\.com/\S+")


def check_forbidden_words(content: str) -> Tuple[bool, list]:
    """禁止ワードが含まれていないか確認"""
    found = [w for w in FORBIDDEN_WORDS if w in content]
    return len(found) == 0, found


def check_preachy_tone(content: str) -> Tuple[bool, list]:
    """上から目線・説教口調でないか確認"""
    found = [p for p in PREACHY_PATTERNS if re.search(p, content)]
    return len(found) == 0, found


def check_line_count(content: str, min_lines: int = 10, max_lines: int = 15) -> Tuple[bool, int]:
    """行数が10〜15行の範囲内か確認（空行を含む）"""
    lines = content.strip().split("\n")
    count = len(lines)
    return min_lines <= count <= max_lines, count


def check_note_link(content: str, post_type: str) -> Tuple[bool, bool]:
    """
    誘導型以外にnoteリンクが入っていないか確認
    Returns: (is_ok, has_link)
    """
    has_link = bool(NOTE_URL_PATTERN.search(content))
    if post_type == "誘導型":
        return True, has_link
    return not has_link, has_link


def run_all_checks(post: dict, config: dict) -> Tuple[bool, list]:
    """
    すべてのチェックを実行する
    Returns: (passed, error_messages)
    """
    errors = []
    content = post["content"]
    post_type = post["type"]
    min_lines = config["quality_check"]["min_lines"]
    max_lines = config["quality_check"]["max_lines"]

    ok, found_words = check_forbidden_words(content)
    if not ok:
        errors.append(f"禁止ワード検出: {found_words}")

    ok, found_patterns = check_preachy_tone(content)
    if not ok:
        errors.append(f"説教口調パターン検出: {found_patterns}")

    ok, line_count = check_line_count(content, min_lines, max_lines)
    if not ok:
        errors.append(f"行数エラー: {line_count}行（{min_lines}〜{max_lines}行が必要）")

    ok, has_link = check_note_link(content, post_type)
    if not ok:
        errors.append(f"誘導型以外にnoteリンクが含まれています")

    return len(errors) == 0, errors
