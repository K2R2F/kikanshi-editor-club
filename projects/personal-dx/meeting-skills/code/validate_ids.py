#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_ids.py
議事録作成Skills向け S-ID / M-ID 採番・整合性点検ツール

目的
----
1. S-ID / M-ID の自動採番
2. 重複・順序・欠番の点検
3. M-ID → S-ID 参照の点検
4. 議事録中の source コメントに含まれる M-ID / S-ID の参照点検

想定するMarkdown表記
----------------------
Scene:
    ## S-001
    - Scene ID：S-001          # 行内記載も検出
    ## S-AUTO                 # 自動採番対象
    ## {{S-ID}}               # 自動採番対象

Meaning Unit:
    ### M-001
    - M-ID：M-001
    ### M-AUTO
    ### {{M-ID}}

M-ID から Scene への参照:
    - Scene：S-005
    - Scene: S-005

議事録から根拠への非表示参照:
    <!-- source: M-023, M-024 / S-007 -->

基本方針
--------
- デフォルトの採番は、AUTOプレースホルダーだけを書き換える。
- 既存IDの再採番は --renumber を明示した場合だけ行う。
- --renumber は既存参照も同一ファイル内で可能な範囲で追随更新するが、
  外部ファイルからの参照は更新できないため、通常運用では推奨しない。
- 点検はファイル内容を変更しない。
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

ID_WIDTH = 3

S_ID_RE = re.compile(r"\bS-(\d{3,})\b")
M_ID_RE = re.compile(r"\bM-(\d{3,})\b")

# 採番対象は意図的なプレースホルダーだけに限定する。
S_AUTO_RE = re.compile(r"(?:S-AUTO|\{\{S-ID\}\})")
M_AUTO_RE = re.compile(r"(?:M-AUTO|\{\{M-ID\}\})")

# M-ID項目内の Scene 参照を検出する。
SCENE_REF_RE = re.compile(
    r"^\s*[-*]?\s*(?:Scene|Scene\s*ID|シーン|シーンID)\s*[：:]\s*(S-\d{3,})\b",
    re.IGNORECASE,
)

SOURCE_COMMENT_RE = re.compile(
    r"<!--\s*source\s*:\s*(.*?)\s*-->",
    re.IGNORECASE,
)

HEADING_S_RE = re.compile(r"^\s*#{1,6}\s+(S-\d{3,})\b")
HEADING_M_RE = re.compile(r"^\s*#{1,6}\s+(M-\d{3,})\b")

@dataclasses.dataclass
class Issue:
    level: str       # ERROR / WARN / INFO
    code: str
    message: str
    file: str | None = None
    line: int | None = None

    def format(self) -> str:
        loc = ""
        if self.file:
            loc = self.file
            if self.line:
                loc += f":{self.line}"
            loc += ": "
        return f"[{self.level}] {self.code}: {loc}{self.message}"


def natural_id_key(value: str) -> int:
    return int(value.split("-")[1])


def fmt_id(prefix: str, n: int) -> str:
    return f"{prefix}-{n:0{ID_WIDTH}d}"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str, backup: bool) -> None:
    if backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)
    path.write_text(text, encoding="utf-8")


def collect_ids(text: str, prefix: str) -> list[str]:
    regex = S_ID_RE if prefix == "S" else M_ID_RE
    return [f"{prefix}-{m.group(1)}" for m in regex.finditer(text)]


def collect_defined_heading_ids(text: str, prefix: str) -> list[tuple[str, int]]:
    regex = HEADING_S_RE if prefix == "S" else HEADING_M_RE
    out: list[tuple[str, int]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        m = regex.match(line)
        if m:
            out.append((m.group(1), line_no))
    return out


def next_available_number(existing: Iterable[str], prefix: str) -> int:
    nums = [natural_id_key(x) for x in existing if x.startswith(prefix + "-")]
    return max(nums, default=0) + 1


def assign_placeholders(text: str, prefix: str) -> tuple[str, list[tuple[str, str]]]:
    """
    AUTOプレースホルダーを文書順に採番する。
    returns: (new_text, [(placeholder_repr, assigned_id), ...])
    """
    auto_re = S_AUTO_RE if prefix == "S" else M_AUTO_RE
    existing = set(collect_ids(text, prefix))
    next_no = next_available_number(existing, prefix)
    assigned: list[tuple[str, str]] = []

    def repl(match: re.Match[str]) -> str:
        nonlocal next_no
        while fmt_id(prefix, next_no) in existing:
            next_no += 1
        new_id = fmt_id(prefix, next_no)
        existing.add(new_id)
        assigned.append((match.group(0), new_id))
        next_no += 1
        return new_id

    return auto_re.sub(repl, text), assigned


def renumber_defined_ids(text: str, prefix: str) -> tuple[str, dict[str, str]]:
    """
    見出しとして定義されたIDを文書順に 001.. へ再採番し、
    同一ファイル内の参照も置換する。

    注意:
    - 同じ旧IDが複数定義されている場合は曖昧なので例外。
    - 外部ファイルの参照は更新できない。
    """
    heading_re = HEADING_S_RE if prefix == "S" else HEADING_M_RE
    lines = text.splitlines(keepends=True)
    defs: list[str] = []
    for line in lines:
        m = heading_re.match(line)
        if m:
            defs.append(m.group(1))

    duplicates = [x for x, c in Counter(defs).items() if c > 1]
    if duplicates:
        raise ValueError(
            f"{prefix}-ID の重複定義があるため再採番できません: {', '.join(duplicates)}"
        )

    mapping = {old: fmt_id(prefix, i) for i, old in enumerate(defs, 1)}
    if not mapping:
        return text, {}

    # 一時トークンを使って連鎖置換を防ぐ。
    tmp_map = {old: f"__TMP_{prefix}_{i:06d}__" for i, old in enumerate(mapping, 1)}
    new_text = text
    id_re = S_ID_RE if prefix == "S" else M_ID_RE

    def to_tmp(match: re.Match[str]) -> str:
        old = f"{prefix}-{match.group(1)}"
        return tmp_map.get(old, old)

    new_text = id_re.sub(to_tmp, new_text)
    for old, tmp in tmp_map.items():
        new_text = new_text.replace(tmp, mapping[old])

    return new_text, mapping


def check_duplicate_defined_ids(
    path: Path, text: str, prefix: str
) -> list[Issue]:
    defs = collect_defined_heading_ids(text, prefix)
    counts = Counter(x for x, _ in defs)
    issues: list[Issue] = []
    for ident, count in counts.items():
        if count > 1:
            lines = [str(line) for value, line in defs if value == ident]
            issues.append(Issue(
                "ERROR", f"{prefix}001",
                f"{ident} が {count} 回定義されています（行 {', '.join(lines)}）。",
                str(path),
            ))
    return issues


def check_order_and_gaps(
    path: Path, text: str, prefix: str
) -> list[Issue]:
    defs = collect_defined_heading_ids(text, prefix)
    issues: list[Issue] = []
    if not defs:
        return issues

    nums = [natural_id_key(x) for x, _ in defs]
    if nums != sorted(nums):
        issues.append(Issue(
            "ERROR", f"{prefix}002",
            f"{prefix}-ID が文書中で時系列順になっていません: "
            + ", ".join(x for x, _ in defs),
            str(path),
        ))

    unique_nums = sorted(set(nums))
    expected = list(range(unique_nums[0], unique_nums[-1] + 1))
    missing = [n for n in expected if n not in unique_nums]
    if missing:
        issues.append(Issue(
            "WARN", f"{prefix}003",
            f"{prefix}-ID に欠番があります: "
            + ", ".join(fmt_id(prefix, n) for n in missing),
            str(path),
        ))

    if unique_nums and unique_nums[0] != 1:
        issues.append(Issue(
            "WARN", f"{prefix}004",
            f"{prefix}-ID の先頭が {fmt_id(prefix, unique_nums[0])} です。"
            f"通常は {prefix}-001 から開始します。",
            str(path),
        ))
    return issues


def check_m_to_s_refs(
    m_path: Path, m_text: str, s_text: str
) -> list[Issue]:
    valid_s = {x for x, _ in collect_defined_heading_ids(s_text, "S")}
    issues: list[Issue] = []
    current_m: str | None = None

    for line_no, line in enumerate(m_text.splitlines(), 1):
        m_heading = HEADING_M_RE.match(line)
        if m_heading:
            current_m = m_heading.group(1)

        ref = SCENE_REF_RE.match(line)
        if ref:
            s_id = ref.group(1)
            if s_id not in valid_s:
                context = f"{current_m}: " if current_m else ""
                issues.append(Issue(
                    "ERROR", "REF001",
                    f"{context}存在しない Scene ID {s_id} を参照しています。",
                    str(m_path), line_no,
                ))
    return issues


def check_source_comments(
    minutes_path: Path,
    minutes_text: str,
    valid_m: set[str],
    valid_s: set[str],
) -> list[Issue]:
    issues: list[Issue] = []
    for line_no, line in enumerate(minutes_text.splitlines(), 1):
        for comment in SOURCE_COMMENT_RE.finditer(line):
            body = comment.group(1)
            m_refs = {f"M-{m.group(1)}" for m in M_ID_RE.finditer(body)}
            s_refs = {f"S-{m.group(1)}" for m in S_ID_RE.finditer(body)}

            for m_id in sorted(m_refs, key=natural_id_key):
                if m_id not in valid_m:
                    issues.append(Issue(
                        "ERROR", "REF002",
                        f"source コメントが存在しない M-ID {m_id} を参照しています。",
                        str(minutes_path), line_no,
                    ))
            for s_id in sorted(s_refs, key=natural_id_key):
                if s_id not in valid_s:
                    issues.append(Issue(
                        "ERROR", "REF003",
                        f"source コメントが存在しない S-ID {s_id} を参照しています。",
                        str(minutes_path), line_no,
                    ))
    return issues


def check_placeholders(path: Path, text: str) -> list[Issue]:
    issues: list[Issue] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if S_AUTO_RE.search(line):
            issues.append(Issue(
                "WARN", "AUTO001",
                "未採番の S-ID プレースホルダーがあります。",
                str(path), line_no,
            ))
        if M_AUTO_RE.search(line):
            issues.append(Issue(
                "WARN", "AUTO002",
                "未採番の M-ID プレースホルダーがあります。",
                str(path), line_no,
            ))
    return issues


def check_project(
    scene_path: Path | None,
    meaning_path: Path | None,
    minutes_path: Path | None,
) -> list[Issue]:
    issues: list[Issue] = []

    s_text = read_text(scene_path) if scene_path else ""
    m_text = read_text(meaning_path) if meaning_path else ""
    min_text = read_text(minutes_path) if minutes_path else ""

    if scene_path:
        issues.extend(check_placeholders(scene_path, s_text))
        issues.extend(check_duplicate_defined_ids(scene_path, s_text, "S"))
        issues.extend(check_order_and_gaps(scene_path, s_text, "S"))

    if meaning_path:
        issues.extend(check_placeholders(meaning_path, m_text))
        issues.extend(check_duplicate_defined_ids(meaning_path, m_text, "M"))
        issues.extend(check_order_and_gaps(meaning_path, m_text, "M"))

    if scene_path and meaning_path:
        issues.extend(check_m_to_s_refs(meaning_path, m_text, s_text))

    if minutes_path:
        issues.extend(check_placeholders(minutes_path, min_text))
        valid_m = {x for x, _ in collect_defined_heading_ids(m_text, "M")}
        valid_s = {x for x, _ in collect_defined_heading_ids(s_text, "S")}
        issues.extend(check_source_comments(minutes_path, min_text, valid_m, valid_s))

    return issues


def command_number(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"エラー: ファイルがありません: {path}", file=sys.stderr)
        return 2

    text = read_text(path)
    original = text
    all_assigned: list[tuple[str, str]] = []

    prefixes = []
    if args.type in ("scene", "both"):
        prefixes.append("S")
    if args.type in ("meaning", "both"):
        prefixes.append("M")

    try:
        if args.renumber:
            for prefix in prefixes:
                text, mapping = renumber_defined_ids(text, prefix)
                if mapping:
                    print(f"{prefix}-ID 再採番:")
                    for old, new in mapping.items():
                        print(f"  {old} -> {new}")
        else:
            for prefix in prefixes:
                text, assigned = assign_placeholders(text, prefix)
                all_assigned.extend(assigned)

        if text == original:
            print("変更対象はありませんでした。")
            return 0

        if args.dry_run:
            print(text)
            return 0

        write_text(path, text, backup=not args.no_backup)
        if all_assigned:
            print("採番:")
            for old, new in all_assigned:
                print(f"  {old} -> {new}")
        print(f"更新しました: {path}")
        if not args.no_backup:
            print(f"バックアップ: {path.with_suffix(path.suffix + '.bak')}")
        return 0

    except ValueError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 2


def command_check(args: argparse.Namespace) -> int:
    scene = Path(args.scene) if args.scene else None
    meaning = Path(args.meaning) if args.meaning else None
    minutes = Path(args.minutes) if args.minutes else None

    for p in [scene, meaning, minutes]:
        if p and not p.exists():
            print(f"エラー: ファイルがありません: {p}", file=sys.stderr)
            return 2

    if not any([scene, meaning, minutes]):
        print("エラー: --scene / --meaning / --minutes のいずれかを指定してください。",
              file=sys.stderr)
        return 2

    issues = check_project(scene, meaning, minutes)

    if not issues:
        print("OK: S-ID / M-ID / 参照関係に問題は見つかりませんでした。")
        return 0

    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    issues.sort(key=lambda x: (order.get(x.level, 9), x.file or "", x.line or 0))
    for issue in issues:
        print(issue.format())

    errors = sum(i.level == "ERROR" for i in issues)
    warns = sum(i.level == "WARN" for i in issues)
    print(f"\n点検結果: ERROR={errors}, WARN={warns}")

    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="議事録作成Skills向け S-ID / M-ID 採番・整合性点検ツール"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    number = sub.add_parser("number", help="AUTOプレースホルダーにIDを採番する")
    number.add_argument("file", help="対象Markdownファイル")
    number.add_argument(
        "--type",
        choices=["scene", "meaning", "both"],
        default="both",
        help="採番するID種別（既定: both）",
    )
    number.add_argument(
        "--renumber",
        action="store_true",
        help="既存見出しIDを文書順に001から再採番する（通常は非推奨）",
    )
    number.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイルを書き換えず、変更後の内容を標準出力する",
    )
    number.add_argument(
        "--no-backup",
        action="store_true",
        help="書換え前の .bak バックアップを作らない",
    )
    number.set_defaults(func=command_number)

    check = sub.add_parser("check", help="IDと参照関係を点検する")
    check.add_argument("--scene", help="02_シーン構造分析.md")
    check.add_argument("--meaning", help="03_議事内容整理.md")
    check.add_argument("--minutes", help="04_議事録.md")
    check.set_defaults(func=command_check)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
