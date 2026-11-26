#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LoonRules 第三方 Loon 规则自动整合脚本。

数据源（只取 Loon 格式的规则）：

1. QuixoticHeart/rule-set
   - 分支 ruleset，目录 loon/，共约 52 个 .list 文件。
   - 文件以 GitHub raw 方式逐个下载。

2. blackmatrix7/ios_rule_script
   - 分支 master，目录 rule/Loon/，共 668 个分类目录。
   - 每个分类通常包含：
       <Category>.list         规则（DOMAIN-KEYWORD / USER-AGENT / IP-CIDR 等）
       <Category>_Domain.list  域名列表（.example.com 表示后缀，example.com 表示精确）
       <Category>_Resolve.list 与 <Category>.list 相同，但 IP 规则不带 no-resolve
     部分分类只有 <Category>.list。
   - 镜像时保留上游目录与文件名；统一库则把同一分类的三份内容按
     <Category>.list → _Domain.list → _Resolve.list 的顺序合并去重。

产物目录（静态注释头，不含时间戳；内容不变则文件不变）：

  Rules/QuixoticHeart/<name>.list                 来源一镜像
  Rules/blackmatrix7/<Category>/<file>.list       来源二镜像（保留上游目录/文件名）
  Rules/Unified/<name>.list                       统一规则库（同名分类合并，来源一优先）
  Rules/INDEX.md                                  自动生成的索引与一键导入链接
  Rules/CONFLICTS.md                              去重统计、冲突与失败清单
  Rules/.sync-manifest.json                       机器可读清单（无时间戳，可复现）

去重与冲突规则：

  * 单个文件内：完全相同的 (规则类型, 值, 参数) 只保留第一次出现，顺序不变；
    域名列表文件按整行去重。
  * 统一库：分类名归一化（忽略大小写与标点）后合并；先来源一、后来源二，
    重复项保留来源一；同一域名在两边类型不同时记入 CONFLICTS.md，保留来源一。

仅依赖 Python 标准库，可在 GitHub Actions ubuntu-latest 或本地直接运行。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# 配置（如需换源/换目录，改这里即可）
# --------------------------------------------------------------------------

HTTP_TIMEOUT = 30          # 单次请求超时（秒）
HTTP_RETRIES = 3           # 失败重试次数
HTTP_WORKERS = 6           # 并发下载数
USER_AGENT = "LoonRules-sync/1.0 (+https://github.com/moyuzaime/LoonRules)"

CONFIG = {
    "quixoticheart": {
        "label": "QuixoticHeart/rule-set",
        "repo": "QuixoticHeart/rule-set",
        "branch": "ruleset",
        "subdir": "loon",
        "ext": ".list",
        "out": "Rules/QuixoticHeart",
        "tree_api": "https://api.github.com/repos/QuixoticHeart/rule-set/git/trees/ruleset?recursive=1",
        "raw_base": "https://raw.githubusercontent.com/QuixoticHeart/rule-set/ruleset/",
        "readme": "https://raw.githubusercontent.com/QuixoticHeart/rule-set/ruleset/README.md",
    },
    "blackmatrix7": {
        "label": "blackmatrix7/ios_rule_script",
        "repo": "blackmatrix7/ios_rule_script",
        "branch": "master",
        "subdir": "rule/Loon",
        "ext": ".list",
        "out": "Rules/blackmatrix7",
        # 先取 rule/Loon 的 tree sha，再递归列出全部 .list（2 次 API 调用）
        "parent_api": "https://api.github.com/repos/blackmatrix7/ios_rule_script/contents/rule",
        "tree_api": "https://api.github.com/repos/blackmatrix7/ios_rule_script/git/trees/{sha}?recursive=1",
        "listing_api": "https://api.github.com/repos/blackmatrix7/ios_rule_script/contents/rule/Loon",
        "readme": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/README.md",
        "raw_base": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/",
        # 同一分类下三个文件的固定后缀，按合并顺序排列
        "suffixes": ["", "_Domain", "_Resolve"],
    },
    "unified": {
        "label": "统一规则库",
        "out": "Rules/Unified",
        "ext": ".list",
        "priority": ["quixoticheart", "blackmatrix7"],
        "index": "Rules/INDEX.md",
        "conflicts": "Rules/CONFLICTS.md",
        "manifest": "Rules/.sync-manifest.json",
    },
}

# 允许用环境变量覆盖（便于本地用 http.server 做离线校验）
ENV_OVERRIDES = {
    "QX_TREE_API": ("quixoticheart", "tree_api"),
    "QX_RAW_BASE": ("quixoticheart", "raw_base"),
    "QX_README": ("quixoticheart", "readme"),
    "BMX_LISTING_API": ("blackmatrix7", "listing_api"),
    "BMX_PARENT_API": ("blackmatrix7", "parent_api"),
    "BMX_TREE_API": ("blackmatrix7", "tree_api"),
    "BMX_RAW_BASE": ("blackmatrix7", "raw_base"),
    "BMX_README": ("blackmatrix7", "readme"),
}


def config_value(section: str, key: str) -> str:
    env_key = next((k for k, v in ENV_OVERRIDES.items() if v == (section, key)), None)
    if env_key and os.environ.get(env_key):
        return os.environ[env_key]
    return CONFIG[section][key]


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


class FetchError(RuntimeError):
    pass


def _request_headers(url: str) -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + token
    return headers


def fetch_text(
    url: str,
    *,
    timeout: int = HTTP_TIMEOUT,
    retries: int = HTTP_RETRIES,
    allow_404: bool = False,
) -> str | None:
    """下载文本；allow_404 时 404 返回 None 而不是抛异常。"""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_request_headers(url))
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8-sig", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and allow_404:
                return None
            last_error = exc
            if exc.code == 429:  # 触发限流时退避更久
                time.sleep(8 * (attempt + 1))
                continue
            if 400 <= exc.code < 500 and exc.code != 408:
                break
        except Exception as exc:  # noqa: BLE001 - 网络错误统一重试
            last_error = exc
        if attempt + 1 < retries:
            time.sleep(1.0 + attempt)
    raise FetchError(f"{url} -> {last_error}")


# --------------------------------------------------------------------------
# 规则解析
# --------------------------------------------------------------------------

RULE_RE = re.compile(r"^\s*([A-Z][A-Z0-9-]*)\s*,(.*)$")
COMMENT_PREFIXES = ("#", ";", "//")
# 只有这些「域名类」规则才存在跨来源同值不同类型的问题
DOMAIN_RULE_TYPES = {
    "DOMAIN",
    "DOMAIN-SUFFIX",
    "DOMAIN-KEYWORD",
    "DOMAIN-WILDCARD",
    "DOMAIN-REGEX",
}


def parse_rule(line: str) -> tuple[str, str, tuple[str, ...]] | None:
    """把一行规则解析成 (类型, 值, 参数元组)。不是规则行返回 None。"""
    stripped = line.strip()
    if not stripped or stripped.startswith(COMMENT_PREFIXES):
        return None
    match = RULE_RE.match(stripped)
    if not match:
        return None
    rule_type = match.group(1)
    fields = [part.strip() for part in match.group(2).split(",")]
    if not fields or not fields[0]:
        return None
    value = fields[0]
    params = tuple(sorted(part for part in fields[1:] if part))
    return rule_type, value, params


@dataclass
class CleanResult:
    lines: list[str] = field(default_factory=list)
    rules: int = 0
    duplicates: int = 0
    unparsed: int = 0


def clean_rules(text: str) -> CleanResult:
    """去掉注释/空行，按 (类型, 值, 参数) 去重并保持原顺序。"""
    result = CleanResult()
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for raw_line in normalized.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith(COMMENT_PREFIXES):
            continue
        key = parse_rule(line)
        if key is None:
            result.unparsed += 1
            continue
        if key in seen:
            result.duplicates += 1
            continue
        seen.add(key)
        result.lines.append(line)
        result.rules += 1
    return result


def clean_domain_entries(text: str) -> tuple[list[str], int]:
    """镜像 blackmatrix7 的 _Domain.list：按整行去重，保留 . 前缀语义。"""
    seen: set[str] = set()
    lines: list[str] = []
    duplicates = 0
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith(COMMENT_PREFIXES):
            continue
        if line in seen:
            duplicates += 1
            continue
        seen.add(line)
        lines.append(line)
    return lines, duplicates


def canon_category(name: str) -> str:
    """分类名归一化：忽略大小写与标点，用于跨来源对齐同名分类。"""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def merge_rule_chunks(chunks: list[str]) -> CleanResult:
    """合并 blackmatrix7 同一分类下的多个分片。

    `<name>_Domain.list` 是「域名列表」而不是规则行：以 `.` 开头的是后缀
    （对应 DOMAIN-SUFFIX），不带点的是精确域名（对应 DOMAIN）；规则行原样保留。
    合并时按上述口径转换，并整体去重。
    """
    result = CleanResult()
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for text in chunks:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        for raw_line in normalized.split("\n"):
            line = raw_line.strip()
            if not line or line.startswith(COMMENT_PREFIXES):
                continue
            parsed = parse_rule(line)
            if parsed is None:
                if any(ch.isspace() for ch in line):
                    result.unparsed += 1
                    continue
                if line.startswith("+."):
                    line = "DOMAIN-SUFFIX," + line[2:]
                elif line.startswith("."):
                    line = "DOMAIN-SUFFIX," + line[1:]
                else:
                    line = "DOMAIN," + line
                parsed = parse_rule(line)
                if parsed is None:
                    result.unparsed += 1
                    continue
            if parsed in seen:
                result.duplicates += 1
                continue
            seen.add(parsed)
            result.lines.append(line)
            result.rules += 1
    return result


# --------------------------------------------------------------------------
# 来源一：QuixoticHeart/rule-set
# --------------------------------------------------------------------------


def list_quixoticheart_files() -> list[str]:
    """先走 GitHub API 树，失败则回退到 README 里的 loon 链接。"""
    api = config_value("quixoticheart", "tree_api")
    try:
        payload = fetch_text(api)
        tree = json.loads(payload).get("tree", [])
        names = sorted(
            {
                Path(item["path"]).name
                for item in tree
                if item.get("type") == "blob"
                and str(item.get("path", "")).startswith("loon/")
                and str(item.get("path", "")).endswith(".list")
            }
        )
        if names:
            return names
    except Exception as exc:  # noqa: BLE001
        log(f"[quixoticheart] API 目录读取失败，回退 README：{exc}")

    readme = fetch_text(config_value("quixoticheart", "readme"))
    names = sorted(set(re.findall(r"/loon/([^/\s)\"'<>]+\.list)", readme or "")))
    if not names:
        raise FetchError("QuixoticHeart：无法从 API 或 README 取得 loon/ 文件列表")
    return names


def fetch_source_quixoticheart(limit: int | None = None) -> tuple[dict, list[str]]:
    names = list_quixoticheart_files()
    if limit:
        names = names[:limit]
    raw_base = config_value("quixoticheart", "raw_base").rstrip("/") + "/"
    out_dir = CONFIG["quixoticheart"]["out"]
    log(f"[quixoticheart] 待下载 {len(names)} 个文件")

    def work(name: str) -> tuple[str, str, CleanResult]:
        url = f"{raw_base}loon/{urllib.parse.quote(name)}"
        text = fetch_text(url)
        cleaned = clean_rules(text)
        return name, render_file(
            header=[
                f"来源: {CONFIG['quixoticheart']['label']}@{CONFIG['quixoticheart']['branch']}/"
                f"{CONFIG['quixoticheart']['subdir']}/{name}",
                f"上游: {url}",
                f"规则数: {cleaned.rules}",
            ],
            lines=cleaned.lines,
        ), cleaned

    results: dict[str, dict] = {}
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=HTTP_WORKERS) as pool:
        futures = {pool.submit(work, name): name for name in names}
        for future in as_completed(futures):
            filename = futures[future]
            try:
                fname, text, cleaned = future.result()
            except Exception as exc:  # noqa: BLE001
                log(f"[quixoticheart] {filename} 下载失败：{exc}")
                failed.append(filename)
                continue
            base = fname[: -len(CONFIG["quixoticheart"]["ext"])] if fname.endswith(
                CONFIG["quixoticheart"]["ext"]
            ) else fname
            results[fname] = {
                "source": "quixoticheart",
                "source_label": CONFIG["quixoticheart"]["label"],
                "name": base,
                "path": f"{out_dir}/{fname}",
                "text": text,
                "lines": cleaned.lines,
                "rules": cleaned.rules,
                "duplicates": cleaned.duplicates,
                "unparsed": cleaned.unparsed,
                "upstream": f"{raw_base}loon/{urllib.parse.quote(fname)}",
            }
    if failed and len(failed) > max(1, int(len(names) * 0.2)):
        raise FetchError(
            f"QuixoticHeart：失败 {len(failed)} / {len(names)}，超过 20%，保留现有文件并中止"
        )
    return results, failed


# --------------------------------------------------------------------------
# 来源二：blackmatrix7/ios_rule_script
# --------------------------------------------------------------------------


SUFFIX_RE = re.compile(r"^(?P<stem>.+?)(?P<suffix>_Domain|_Resolve)?\.list$")


def list_blackmatrix7_files() -> list[str]:
    """返回 rule/Loon 下全部 .list 的相对路径。

    形如 `Apple/Apple.list`、`Cloud/AkamaiCloud/AkamaiCloud.list`。
    优先用 Git Trees API 一次列出（2 次 API 调用）；失败时回退为逐目录按固定后缀探测，
    此时会漏掉 Cloud 这类「分组目录」下的子分类，但不会漏掉顶层分类。
    """
    tree_api = config_value("blackmatrix7", "tree_api")
    try:
        parent = json.loads(fetch_text(config_value("blackmatrix7", "parent_api")))
        loon = next(
            item for item in parent
            if item.get("name") == "Loon" and item.get("type") == "dir"
        )
        tree = json.loads(fetch_text(tree_api.format(sha=loon["sha"])))
        if tree.get("truncated"):
            raise FetchError("Git Trees 结果被截断")
        paths = sorted(
            entry["path"]
            for entry in tree.get("tree", [])
            if entry.get("type") == "blob" and entry["path"].endswith(".list")
        )
        if paths:
            return paths
    except Exception as exc:  # noqa: BLE001
        log(f"[blackmatrix7] 递归文件列表读取失败，回退逐目录探测：{exc}")

    listing = json.loads(fetch_text(config_value("blackmatrix7", "listing_api")))
    base = config_value("blackmatrix7", "raw_base").rstrip("/") + "/"
    paths: list[str] = []
    for item in listing:
        if item.get("type") != "dir":
            continue
        category = item["name"]
        for suffix in CONFIG["blackmatrix7"]["suffixes"]:
            filename = f"{category}{suffix}.list"
            url = f"{base}{urllib.parse.quote(category)}/{urllib.parse.quote(filename)}"
            try:
                if fetch_text(url, retries=1, allow_404=True):
                    paths.append(f"{category}/{filename}")
            except FetchError:
                continue
    if not paths:
        raise FetchError("blackmatrix7：无法取得 rule/Loon 下的 .list 文件列表")
    return sorted(paths)


def group_blackmatrix7_files(paths: list[str]) -> "OrderedDict[tuple[str, str], dict[str, str]]":
    """把 `<dir>/<stem>{_Domain,_Resolve,}.list` 归到同一分类下。"""
    groups: "OrderedDict[tuple[str, str], dict[str, str]]" = OrderedDict()
    for rel in paths:
        directory, filename = rel.rsplit("/", 1)
        match = SUFFIX_RE.match(filename)
        if not match:
            continue
        stem = match.group("stem")
        suffix = match.group("suffix") or ""
        groups.setdefault((directory, stem), {})[suffix] = filename
    return groups


def fetch_source_blackmatrix7(limit: int | None = None) -> tuple[dict, list[dict], list[str], dict]:
    paths = list_blackmatrix7_files()
    groups = group_blackmatrix7_files(paths)
    if limit:
        groups = OrderedDict(list(groups.items())[:limit])
    base = config_value("blackmatrix7", "raw_base").rstrip("/") + "/"
    suffixes = CONFIG["blackmatrix7"]["suffixes"]
    log(
        f"[blackmatrix7] 待处理 {len(groups)} 个分类 / "
        f"{sum(len(files) for files in groups.values())} 个 .list"
    )

    def work(rel: str) -> tuple[str, str]:
        return rel, fetch_text(base + urllib.parse.quote(rel, safe="/"))

    texts: dict[str, str] = {}
    failed_files: set[str] = set()
    tasks = [
        f"{directory}/{filename}"
        for (directory, _stem), files in groups.items()
        for filename in files.values()
    ]
    with ThreadPoolExecutor(max_workers=HTTP_WORKERS) as pool:
        futures = {pool.submit(work, rel): rel for rel in tasks}
        for future in as_completed(futures):
            rel = futures[future]
            try:
                _, text = future.result()
            except Exception as exc:  # noqa: BLE001
                log(f"[blackmatrix7] {rel} 下载失败：{exc}")
                failed_files.add(rel)
                continue
            texts[rel] = text

    mirror: dict[str, dict] = {}
    unified_items: list[dict] = []
    missing: list[str] = []
    totals = {
        "categories": 0,
        "rules": 0,
        "domain_entries": 0,
        "files": 0,
        "duplicates": 0,
        "unparsed": 0,
    }

    for (directory, stem), files in groups.items():
        rels = [f"{directory}/{files[suffix]}" for suffix in suffixes if suffix in files]
        if any(rel in failed_files or rel not in texts for rel in rels):
            missing.append(f"{directory}/{stem}")
            continue
        totals["categories"] += 1
        parts: list[str] = []
        for suffix in suffixes:
            if suffix not in files:
                continue
            filename = files[suffix]
            rel = f"{directory}/{filename}"
            text = texts[rel]
            parts.append(text)
            url = base + urllib.parse.quote(rel, safe="/")
            if suffix == "_Domain":
                lines, duplicates = clean_domain_entries(text)
                kind, count, label = "domain", len(lines), "条目数"
                totals["domain_entries"] += count
            else:
                cleaned = clean_rules(text)
                lines, duplicates, count = cleaned.lines, cleaned.duplicates, cleaned.rules
                kind, label = "rules", "规则数"
                totals["rules"] += count
                totals["unparsed"] += cleaned.unparsed
            totals["duplicates"] += duplicates
            totals["files"] += 1
            rendered = render_file(
                header=[
                    f"来源: {CONFIG['blackmatrix7']['label']} "
                    f"{CONFIG['blackmatrix7']['subdir']}/{rel}",
                    f"上游: {url}",
                    f"{label}: {count}",
                ],
                lines=lines,
            )
            mirror[rel] = {
                "source": "blackmatrix7",
                "source_label": CONFIG["blackmatrix7"]["label"],
                "name": stem,
                "filename": filename,
                "rel": rel,
                "kind": kind,
                "path": f"{CONFIG['blackmatrix7']['out']}/{rel}",
                "text": rendered,
                "rules": count,
                "duplicates": duplicates,
                "upstream": url,
                "suffix": suffix,
            }

        merged = merge_rule_chunks(parts)
        unified_items.append({"name": stem, "lines": merged.lines, "count": merged.rules})

    if missing and len(missing) > max(1, int(len(groups) * 0.2)):
        raise FetchError(
            f"blackmatrix7：{len(missing)} / {len(groups)} 个分类下载失败，超过 20%，"
            "保留现有文件并中止"
        )
    return mirror, unified_items, missing, totals


# --------------------------------------------------------------------------
# 文件渲染 / 写入 / 清理
# --------------------------------------------------------------------------


def render_file(header: list[str], lines: list[str]) -> str:
    head = "\n".join("# " + item for item in header)
    body = "\n".join(lines)
    return f"{head}\n{body}\n" if body else f"{head}\n"


def write_if_changed(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == text:
                return False
        except UnicodeDecodeError:
            pass
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def prune_stale(directory: Path, keep: set[str], extensions: tuple[str, ...]) -> list[str]:
    """删除目录中不在 keep 里的文件（顶层）。"""
    removed: list[str] = []
    if not directory.is_dir():
        return removed
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix not in extensions:
            continue
        if path.name not in keep:
            path.unlink()
            removed.append(str(path))
    return removed


def prune_tree(directory: Path, keep: set[str], extensions: tuple[str, ...]) -> list[str]:
    """删除目录树中不在 keep（相对路径）里的文件，并清理空目录。"""
    removed: list[str] = []
    if not directory.is_dir():
        return removed
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix not in extensions:
            continue
        rel = path.relative_to(directory).as_posix()
        if rel not in keep:
            path.unlink()
            removed.append(str(path))
    for sub in sorted((p for p in directory.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            if not any(sub.iterdir()):
                sub.rmdir()
        except OSError:
            pass
    return removed


# --------------------------------------------------------------------------
# 统一规则库
# --------------------------------------------------------------------------


def build_unified(source_items: dict[str, list[dict]], priority: list[str]) -> tuple[dict[str, dict], dict]:
    """按归一化分类名合并多个来源，来源一优先。

    source_items[source] = [{"name": 分类名, "lines": [规则行, ...]}, ...]
    """
    by_category: "OrderedDict[str, dict]" = OrderedDict()
    stats = {
        "duplicates_across_sources": 0,
        "conflicts": [],
        "source_files": {},
    }

    for source in priority:
        items = source_items.get(source, [])
        stats["source_files"][source] = len(items)
        for item in sorted(items, key=lambda entry: entry["name"].lower()):
            key = canon_category(item["name"])
            category = by_category.setdefault(
                key,
                {
                    "display": item["name"],
                    "origin": {},
                    "lines": [],
                    "seen": set(),
                    "values": {},
                    "count": 0,
                },
            )
            category["origin"][source] = item["name"]
            for line in item["lines"]:
                parsed = parse_rule(line)
                if parsed is None:
                    continue
                rule_type, value, _params = parsed
                if parsed in category["seen"]:
                    stats["duplicates_across_sources"] += 1
                    continue
                category["seen"].add(parsed)
                category["lines"].append(line)
                category["count"] += 1
                if rule_type in DOMAIN_RULE_TYPES:
                    category["values"].setdefault(value.lower(), []).append((rule_type, source))

    unified: dict[str, dict] = {}
    for category in by_category.values():
        name = category["display"]
        origin_notes = []
        for source in priority:
            if source in category["origin"]:
                origin_notes.append(f"{CONFIG[source]['label']} {category['origin'][source]}")
        header = [
            f"统一规则库 | 分类: {name}",
            "合并来源: " + "; ".join(origin_notes),
            f"规则数: {category['count']}",
        ]
        unified[f"{name}{CONFIG['unified']['ext']}"] = {
            "name": name,
            "text": render_file(header=header, lines=category["lines"]),
            "rules": category["count"],
            "origins": origin_notes,
            "path": f"{CONFIG['unified']['out']}/{name}{CONFIG['unified']['ext']}",
        }
        for value, occurrences in category["values"].items():
            types = {item[0] for item in occurrences}
            sources = {item[1] for item in occurrences}
            # 只报告「两个来源对同一域名用了不同规则类型」的情况；
            # 单一来源内部的多类型写法属于上游自身内容，不算合并冲突。
            if len(types) > 1 and len(sources) > 1:
                stats["conflicts"].append(
                    {
                        "category": name,
                        "value": value,
                        "types": sorted(types),
                        "detail": "; ".join(f"{t}({s})" for t, s in occurrences),
                    }
                )
    return unified, stats


# --------------------------------------------------------------------------
# 索引 / 报告 / 清单
# --------------------------------------------------------------------------


def raw_url(repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{urllib.parse.quote(path)}"


def import_link(url: str) -> str:
    return "https://www.nsloon.com/openloon/import?rules=" + urllib.parse.quote(url, safe="")


def build_index(qx: dict, bmx: dict, unified: dict, totals: dict) -> str:
    repo, branch = "moyuzaime/LoonRules", "main"
    categories: "OrderedDict[tuple[str, str], dict[str, dict]]" = OrderedDict()
    for item in bmx.values():
        directory = item["rel"].rsplit("/", 1)[0]
        categories.setdefault((directory, item["name"]), {})[item["filename"]] = item

    lines = [
        "# Loon 规则索引",
        "",
        "> 本文件由 `scripts/sync.py` 自动生成，请勿手工编辑；"
        "更新流程见 [docs/THIRD_PARTY_RULES.md](../docs/THIRD_PARTY_RULES.md)。",
        "",
        "## 概览",
        "",
        "| 目录 | 规则集 | 规则条数 |",
        "| --- | ---: | ---: |",
        f"| `Rules/QuixoticHeart` | {len(qx)} | {totals['quixoticheart']} |",
        f"| `Rules/blackmatrix7` | {len(categories)} 个分类 / {len(bmx)} 个文件 | "
        f"{totals['blackmatrix7']} 条 + {totals['blackmatrix7_domain']} 域名 |",
        f"| `Rules/Unified` | {len(unified)} | {totals['unified']} |",
        "",
        "## 统一规则库",
        "",
        "同名分类已合并去重（来源一优先）；冲突见 [CONFLICTS.md](CONFLICTS.md)。",
        "",
        "| # | 分类 | 规则数 | 合并来源 | 一键导入 |",
        "| ---: | --- | ---: | --- | --- |",
    ]
    for index, key in enumerate(sorted(unified, key=str.lower), start=1):
        item = unified[key]
        url = raw_url(repo, branch, item["path"])
        origins = "、".join(item["origins"])
        lines.append(
            f"| {index} | `{item['name']}` | {item['rules']} | {origins} | [导入]({import_link(url)}) |"
        )

    lines += [
        "",
        f"## 来源镜像 · {CONFIG['quixoticheart']['label']}",
        "",
        "| # | 文件 | 规则数 | 一键导入 |",
        "| ---: | --- | ---: | --- |",
    ]
    for index, key in enumerate(sorted(qx, key=str.lower), start=1):
        item = qx[key]
        url = raw_url(repo, branch, item["path"])
        lines.append(
            f"| {index} | [`{item['name']}.list`](QuixoticHeart/{item['name']}.list) | {item['rules']} | "
            f"[导入]({import_link(url)}) |"
        )

    lines += [
        "",
        f"## 来源镜像 · {CONFIG['blackmatrix7']['label']}",
        "",
        "每个分类最多三个文件：`.list`（规则）、`_Domain.list`（域名列表）、`_Resolve.list`"
        "（与 `.list` 相同、IP 规则不带 no-resolve）；保留上游目录结构。",
        "",
        "| # | 分类 | 文件 | 条目 | 一键导入 |",
        "| ---: | --- | --- | ---: | --- |",
    ]
    for index, key in enumerate(
        sorted(categories, key=lambda item: (item[1].lower(), item[0])), start=1
    ):
        _directory, category = key
        files = categories[key]
        file_links = []
        import_links = []
        total = 0
        for filename in sorted(files, key=lambda name: (name != f"{category}.list", name)):
            item = files[filename]
            total += item["rules"]
            file_links.append(f"[{filename}](blackmatrix7/{item['rel']})")
            import_links.append(f"[{filename}]({import_link(raw_url(repo, branch, item['path']))})")
        lines.append(
            f"| {index} | `{category}` | {' · '.join(file_links)} | {total} | {' · '.join(import_links)} |"
        )

    lines.append("")
    return "\n".join(lines)


def build_conflicts(
    unified_stats: dict,
    qx_stats: dict,
    bmx_stats: dict,
    qx_failed: list[str],
    missing: list[str],
) -> str:
    lines = [
        "# 冲突与去重报告",
        "",
        "> 本文件由 `scripts/sync.py` 自动生成，请勿手工编辑。",
        "",
        "## 统计",
        "",
        "| 项目 | 数量 |",
        "| --- | ---: |",
        f"| 来源一文件内去重 | {qx_stats['duplicates']} |",
        f"| 来源二文件内去重 | {bmx_stats['duplicates']} |",
        f"| 来源一无法解析的行 | {qx_stats['unparsed']} |",
        f"| 来源二无法解析的行 | {bmx_stats['unparsed']} |",
        f"| 统一库跨来源重复（保留来源一） | {unified_stats['duplicates_across_sources']} |",
        f"| 统一库跨来源类型冲突 | {len(unified_stats['conflicts'])} |",
        f"| 来源一下载失败文件 | {len(qx_failed)} |",
        f"| 来源二缺失分类 | {len(missing)} |",
        "",
    ]
    if unified_stats["conflicts"]:
        lines += [
            "## 类型冲突",
            "",
            "同一域名在两个来源中使用不同规则类型。统一库保留来源一（QuixoticHeart）写法，"
            "另一写法不再重复收录；如需以来源二为准，请修改 `scripts/sync.py` 中 "
            "`CONFIG['unified']['priority']` 的顺序。",
            "",
            "| 分类 | 域名 | 类型 | 明细 |",
            "| --- | --- | --- | --- |",
        ]
        for item in unified_stats["conflicts"][:500]:
            lines.append(
                f"| {item['category']} | `{item['value']}` | {' / '.join(item['types'])} | {item['detail']} |"
            )
        if len(unified_stats["conflicts"]) > 500:
            lines.append(f"| … | 其余 {len(unified_stats['conflicts']) - 500} 条省略 | | |")
        lines.append("")
    if qx_failed:
        lines += [
            "## 来源一下载失败",
            "",
            "以下规则集本次未取到，已保留上一版本文件：",
            "",
        ]
        lines += [f"- `{name}`" for name in qx_failed[:300]]
        if len(qx_failed) > 300:
            lines.append(f"- … 其余 {len(qx_failed) - 300} 个省略")
        lines.append("")
    if missing:
        lines += [
            "## 来源二缺失分类",
            "",
            "以下分类在 rule/Loon 下存在，但三个 .list 都未取到（已保留上一版本文件）：",
            "",
        ]
        lines += [f"- `{name}`" for name in missing[:300]]
        if len(missing) > 300:
            lines.append(f"- … 其余 {len(missing) - 300} 个省略")
        lines.append("")
    return "\n".join(lines)


def build_manifest(
    qx: dict,
    bmx: dict,
    unified: dict,
    qx_failed: list[str],
    missing: list[str],
    totals: dict,
) -> str:
    def file_fingerprint(item: dict) -> dict:
        data = item["text"].encode("utf-8")
        return {
            "path": item["path"],
            "source": item["source"],
            "name": item["name"],
            "filename": item.get("filename", ""),
            "kind": item.get("kind", "rules"),
            "rules": item["rules"],
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "upstream": item.get("upstream", ""),
        }

    payload = {
        "generator": "scripts/sync.py",
        "sources": {
            "quixoticheart": {
                "repo": CONFIG["quixoticheart"]["repo"],
                "branch": CONFIG["quixoticheart"]["branch"],
                "files": len(qx),
                "failed": sorted(qx_failed),
            },
            "blackmatrix7": {
                "repo": CONFIG["blackmatrix7"]["repo"],
                "branch": CONFIG["blackmatrix7"]["branch"],
                "categories": totals["blackmatrix7_categories"],
                "files": len(bmx),
                "rules": totals["blackmatrix7"],
                "domain_entries": totals["blackmatrix7_domain"],
                "missing": sorted(missing),
            },
        },
        "files": [
            file_fingerprint(item)
            for item in sorted(qx.values(), key=lambda entry: entry["path"])
            + sorted(bmx.values(), key=lambda entry: entry["path"])
        ],
        "unified": [
            {
                "path": item["path"],
                "name": item["name"],
                "rules": item["rules"],
                "origins": item["origins"],
                "sha256": hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
            }
            for item in sorted(unified.values(), key=lambda entry: entry["path"])
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def log(message: str) -> None:
    print(message, flush=True)


def sync(repo_root: Path, *, limit: int | None = None, dry_run: bool = False) -> dict:
    started = time.time()
    qx, qx_failed = fetch_source_quixoticheart(limit=limit)
    bmx, bmx_items, bmx_missing, bmx_totals = fetch_source_blackmatrix7(limit=limit)

    if limit is None:
        # 防御：来源异常大面积失败时不要删除已有文件
        if len(qx) == 0:
            raise FetchError("QuixoticHeart：没有任何文件下载成功，保留现有文件并中止")
        if len(bmx) == 0:
            raise FetchError("blackmatrix7：没有任何文件下载成功，保留现有文件并中止")
        if bmx_missing and bmx_totals["categories"] and len(bmx_missing) > bmx_totals["categories"] * 0.2:
            raise FetchError(
                f"blackmatrix7：缺失 {len(bmx_missing)} 个分类，超过 20%，"
                "为避免误删保留现有文件并中止"
            )

    source_items = {
        "quixoticheart": [
            {"name": item["name"], "lines": item["lines"]} for item in qx.values()
        ],
        "blackmatrix7": bmx_items,
    }
    unified, unified_stats = build_unified(source_items, CONFIG["unified"]["priority"])

    totals = {
        "quixoticheart": sum(item["rules"] for item in qx.values()),
        "blackmatrix7": bmx_totals["rules"],
        "blackmatrix7_domain": bmx_totals["domain_entries"],
        "blackmatrix7_categories": bmx_totals["categories"],
        "unified": sum(item["rules"] for item in unified.values()),
    }
    qx_dupes = sum(item.get("duplicates", 0) for item in qx.values())
    qx_unparsed = sum(item.get("unparsed", 0) for item in qx.values())
    bmx_dupes = bmx_totals["duplicates"]
    bmx_unparsed = bmx_totals["unparsed"]

    index_text = build_index(qx, bmx, unified, totals)
    conflicts_text = build_conflicts(
        unified_stats,
        {"duplicates": qx_dupes, "unparsed": qx_unparsed},
        {"duplicates": bmx_dupes, "unparsed": bmx_unparsed},
        qx_failed,
        bmx_missing,
    )
    manifest_text = build_manifest(qx, bmx, unified, qx_failed, bmx_missing, totals)

    summary = {
        "quixoticheart_files": len(qx),
        "quixoticheart_rules": totals["quixoticheart"],
        "quixoticheart_failed": len(qx_failed),
        "blackmatrix7_categories": totals["blackmatrix7_categories"],
        "blackmatrix7_files": len(bmx),
        "blackmatrix7_rules": totals["blackmatrix7"],
        "blackmatrix7_domain_entries": totals["blackmatrix7_domain"],
        "blackmatrix7_missing": len(bmx_missing),
        "unified_categories": len(unified),
        "unified_rules": totals["unified"],
        "conflicts": len(unified_stats["conflicts"]),
        "duration_seconds": round(time.time() - started, 1),
        "dry_run": dry_run,
    }

    if dry_run:
        return summary

    changed: list[str] = []
    for item in qx.values():
        if write_if_changed(repo_root / item["path"], item["text"]):
            changed.append(item["path"])
    for item in bmx.values():
        if write_if_changed(repo_root / item["path"], item["text"]):
            changed.append(item["path"])
    for item in unified.values():
        if write_if_changed(repo_root / item["path"], item["text"]):
            changed.append(item["path"])

    # 清理上游已删除的规则集（--limit 调试模式或有失败时不做删除，避免误删）
    if limit is None:
        removed = prune_stale(repo_root / CONFIG["quixoticheart"]["out"], set(qx), (".list",))
        if not bmx_missing:
            removed += prune_tree(
                repo_root / CONFIG["blackmatrix7"]["out"], set(bmx), (".list",)
            )
        if not bmx_missing and not qx_failed:
            removed += prune_stale(
                repo_root / CONFIG["unified"]["out"],
                set(unified),
                (CONFIG["unified"]["ext"],),
            )
        changed.extend(os.path.relpath(path, repo_root) for path in removed)

    for rel_path, text in (
        (CONFIG["unified"]["index"], index_text),
        (CONFIG["unified"]["conflicts"], conflicts_text),
        (CONFIG["unified"]["manifest"], manifest_text),
    ):
        if write_if_changed(repo_root / rel_path, text):
            changed.append(rel_path)

    summary["changed_files"] = len(changed)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="整合 QuixoticHeart 与 blackmatrix7 的 Loon 规则")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 个文件/分类（调试用）")
    parser.add_argument("--dry-run", action="store_true", help="只抓取统计，不写文件")
    parser.add_argument("--summary-out", default=None, help="把 JSON 统计写到该路径")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    try:
        summary = sync(repo_root, limit=args.limit, dry_run=args.dry_run)
    except FetchError as exc:
        log(f"[fatal] {exc}")
        return 1

    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    log(payload)
    if args.summary_out:
        out = Path(args.summary_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
