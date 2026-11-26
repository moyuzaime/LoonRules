#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LoonRules 第三方 Loon 规则自动整合脚本。

数据源（只取 Loon 格式的规则）：

1. QuixoticHeart/rule-set
   - 分支 ruleset，目录 loon/，共约 52 个 .list 文件。
   - 文件以 GitHub raw 方式逐个下载。

2. luestr/ShuntRules
   - README 表格中给出 https://rule.kelee.one/Loon/<name>.lsr 共约 668 个规则集。
   - 优先直连 rule.kelee.one 下载。
   - rule.kelee.one 被 Cloudflare 拦截（403/挑战页）时，回退为
     blackmatrix7/ios_rule_script 的 Loon 三件套
       rule/Loon/<name>/<name>.list
       rule/Loon/<name>/<name>_Domain.list
       rule/Loon/<name>/<name>_Resolve.list
     按顺序合并去重重建，语义与 ShuntRules 的“合并规则”一致。

产物目录（均带静态注释头，不含时间戳，内容不变则文件不变）：

  Rules/QuixoticHeart/<name>.list   来源一镜像
  Rules/ShuntRules/<name>.lsr       来源二镜像
  Rules/Unified/<name>.list         统一规则库（同名分类合并，来源一优先）
  Rules/INDEX.md                    自动生成的索引与一键导入链接
  Rules/CONFLICTS.md                冲突与去重报告
  Rules/.sync-manifest.json         机器可读清单（无时间戳，可复现）

去重与冲突规则：

  * 单个文件内：完全相同的 (规则类型, 值, 参数) 只保留第一次出现，顺序不变。
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
    "shuntrules": {
        "label": "luestr/ShuntRules",
        "repo": "luestr/ShuntRules",
        "branch": "main",
        "readme": "https://raw.githubusercontent.com/luestr/ShuntRules/main/README.md",
        "base_url": "https://rule.kelee.one/Loon/",
        "ext": ".lsr",
        "out": "Rules/ShuntRules",
        "fallback_label": "blackmatrix7/ios_rule_script",
        "fallback_base": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/",
        # ShuntRules 的合并来源：三个文件按顺序拼接
        "fallback_parts": ["{name}.list", "{name}_Domain.list", "{name}_Resolve.list"],
    },
    "unified": {
        "label": "统一规则库",
        "out": "Rules/Unified",
        "ext": ".list",
        "priority": ["quixoticheart", "shuntrules"],
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
    "SHUNT_README": ("shuntrules", "readme"),
    "SHUNT_BASE": ("shuntrules", "base_url"),
    "BMX_RAW_BASE": ("shuntrules", "fallback_base"),
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
    allow_403: bool = False,
) -> str | None:
    """下载文本。allow_404/allow_403 时对应状态码返回 None 而不是抛异常。"""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_request_headers(url))
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8-sig", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and allow_404:
                return None
            if exc.code in (403, 401) and allow_403:
                return None
            last_error = exc
            if exc.code == 429:  # 触发限流时退避更久
                time.sleep(8 * (attempt + 1))
                continue
            # 其余 4xx 重试没有意义
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


def canon_category(name: str) -> str:
    """分类名归一化：忽略大小写与标点，用于跨来源对齐同名分类。"""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def merge_rule_chunks(chunks: list[str]) -> CleanResult:
    """合并 ShuntRules 的三个分片。

    blackmatrix7 的 Loon 目录里，`<name>_Domain.list` 是「域名列表」而不是规则行：
    以 `.` 开头的是后缀（对应 DOMAIN-SUFFIX），不带点的是精确域名（对应 DOMAIN）；
    规则行则原样保留。合并时按上述口径转换，并整体去重。
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
# 来源二：luestr/ShuntRules（直连 + blackmatrix7 回退）
# --------------------------------------------------------------------------


def list_shuntrules_names() -> list[str]:
    readme = fetch_text(config_value("shuntrules", "readme"))
    names: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"rule\.kelee\.one/Loon/([^)\s\"'<>]+?)\.lsr", readme or ""):
        name = match.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    if not names:
        raise FetchError("ShuntRules：README 中未解析到任何 Loon 规则链接")
    return names


def probe_shuntrules_direct(name: str) -> bool:
    """用第一个文件探测 rule.kelee.one 是否可直连。"""
    base = config_value("shuntrules", "base_url").rstrip("/") + "/"
    url = base + urllib.parse.quote(name) + ".lsr"
    try:
        fetch_text(url, timeout=15, retries=1)
        return True
    except FetchError as exc:
        log(f"[shuntrules] 直连不可用（{exc}），改用 blackmatrix7 Loon 三件套重建")
        return False


def fetch_shuntrules_file(name: str, direct_ok: bool) -> tuple[str, str | None, dict]:
    """返回 (模式, 原始文本, 细节)。模式：direct / fallback / missing。"""
    base = config_value("shuntrules", "base_url").rstrip("/") + "/"
    url = base + urllib.parse.quote(name) + ".lsr"
    if direct_ok:
        try:
            text = fetch_text(url)
            # 有些 CDN 会用 200 返回挑战页/错误页，解析不出规则就当作失败
            if merge_rule_chunks([text]).rules > 0:
                return "direct", text, {"upstream": url}
            log(f"[shuntrules] {name} 直连内容不是有效规则，尝试回退")
        except FetchError as exc:
            log(f"[shuntrules] {name} 直连失败，尝试回退：{exc}")

    fallback_base = config_value("shuntrules", "fallback_base").rstrip("/") + "/"
    chunks: list[str] = []
    used: list[str] = []
    for pattern in CONFIG["shuntrules"]["fallback_parts"]:
        filename = pattern.format(name=name)
        part_url = f"{fallback_base}{urllib.parse.quote(name)}/{urllib.parse.quote(filename)}"
        try:
            text = fetch_text(part_url, allow_404=True)
        except FetchError as exc:
            log(f"[shuntrules] {name} 回退文件失败：{exc}")
            text = None
        if text:
            chunks.append(text)
            used.append(part_url)
    if not chunks or merge_rule_chunks(chunks).rules == 0:
        return "missing", None, {"upstream": url}
    return "fallback", "\n".join(chunks), {"upstream": url, "fallback_files": used}


def fetch_source_shuntrules(limit: int | None = None) -> tuple[dict, list[str], dict]:
    names = list_shuntrules_names()
    if limit:
        names = names[:limit]
    direct_ok = probe_shuntrules_direct(names[0])
    log(f"[shuntrules] 待处理 {len(names)} 个文件（直连={'是' if direct_ok else '否'}）")

    out_dir = CONFIG["shuntrules"]["out"]
    ext = CONFIG["shuntrules"]["ext"]
    results: dict[str, dict] = {}
    missing: list[str] = []
    modes = {"direct": 0, "fallback": 0}

    with ThreadPoolExecutor(max_workers=HTTP_WORKERS) as pool:
        futures = {pool.submit(fetch_shuntrules_file, name, direct_ok): name for name in names}
        for future in as_completed(futures):
            name = futures[future]
            mode, text, detail = future.result()
            if mode == "missing" or not text:
                missing.append(name)
                continue
            modes[mode] += 1
            cleaned = merge_rule_chunks([text])
            header = [
                f"来源: {CONFIG['shuntrules']['label']} Loon/{name}{ext}",
                f"上游: {detail['upstream']}",
                f"规则数: {cleaned.rules}",
            ]
            results[f"{name}{ext}"] = {
                "source": "shuntrules",
                "source_label": CONFIG["shuntrules"]["label"],
                "name": name,
                "path": f"{out_dir}/{name}{ext}",
                "text": render_file(header=header, lines=cleaned.lines),
                "rules": cleaned.rules,
                "duplicates": cleaned.duplicates,
                "unparsed": cleaned.unparsed,
                "upstream": detail["upstream"],
                "mode": mode,
                "shards": detail.get("fallback_files", []),
            }
    return results, missing, modes


# --------------------------------------------------------------------------
# 文件渲染 / 写入
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


# --------------------------------------------------------------------------
# 统一规则库
# --------------------------------------------------------------------------


def build_unified(entries: dict[str, dict], priority: list[str]) -> tuple[dict[str, dict], dict]:
    """按归一化分类名合并多个来源，来源一优先。"""
    by_category: "OrderedDict[str, dict]" = OrderedDict()
    stats = {
        "duplicates_across_sources": 0,
        "conflicts": [],
        "source_files": {},
    }

    for source in priority:
        source_files = [item for item in entries.values() if item["source"] == source]
        stats["source_files"][source] = len(source_files)
        for item in sorted(source_files, key=lambda entry: entry["name"].lower()):
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
            for line in clean_rules(item["text"]).lines:
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


def build_index(qx: dict, shunt: dict, unified: dict, totals: dict) -> str:
    repo, branch = "moyuzaime/LoonRules", "main"
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
        f"| `Rules/ShuntRules` | {len(shunt)} | {totals['shuntrules']} |",
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

    def mirror_section(title: str, entries: dict, folder: str, ext: str) -> list[str]:
        section = [
            "",
            f"## 来源镜像 · {title}",
            "",
            "| # | 文件 | 规则数 | 一键导入 |",
            "| ---: | --- | ---: | --- |",
        ]
        for index, key in enumerate(sorted(entries, key=str.lower), start=1):
            item = entries[key]
            url = raw_url(repo, branch, item["path"])
            section.append(
                f"| {index} | [`{item['name']}{ext}`]({folder}/{item['name']}{ext}) | {item['rules']} | "
                f"[导入]({import_link(url)}) |"
            )
        return section

    lines += mirror_section(CONFIG["quixoticheart"]["label"], qx, "QuixoticHeart", ".list")
    lines += mirror_section(CONFIG["shuntrules"]["label"], shunt, "ShuntRules", ".lsr")
    lines.append("")
    return "\n".join(lines)


def build_conflicts(
    unified_stats: dict,
    qx_stats: dict,
    shunt_stats: dict,
    missing: list[str],
    qx_failed: list[str],
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
        f"| 来源二文件内去重 | {shunt_stats['duplicates']} |",
        f"| 来源一无法解析的行 | {qx_stats['unparsed']} |",
        f"| 来源二无法解析的行 | {shunt_stats['unparsed']} |",
        f"| 统一库跨来源重复（保留来源一） | {unified_stats['duplicates_across_sources']} |",
        f"| 统一库跨来源类型冲突 | {len(unified_stats['conflicts'])} |",
        f"| 来源一下载失败文件 | {len(qx_failed)} |",
        f"| 来源二下载失败文件 | {len(missing)} |",
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
            "## 来源二下载失败",
            "",
            "以下规则集在直连与 blackmatrix7 回退中均未取到，已保留上一版本文件：",
            "",
        ]
        lines += [f"- `{name}`" for name in missing[:300]]
        if len(missing) > 300:
            lines.append(f"- … 其余 {len(missing) - 300} 个省略")
        lines.append("")
    return "\n".join(lines)


def build_manifest(
    qx: dict,
    shunt: dict,
    unified: dict,
    missing: list[str],
    qx_failed: list[str],
    modes: dict,
) -> str:
    def file_fingerprint(item: dict) -> dict:
        data = item["text"].encode("utf-8")
        return {
            "path": item["path"],
            "source": item["source"],
            "name": item["name"],
            "rules": item["rules"],
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "upstream": item.get("upstream", ""),
            "mode": item.get("mode", "mirror"),
            "shards": item.get("shards", []),
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
            "shuntrules": {
                "repo": CONFIG["shuntrules"]["repo"],
                "branch": CONFIG["shuntrules"]["branch"],
                "files": len(shunt),
                "direct": modes.get("direct", 0),
                "fallback": modes.get("fallback", 0),
                "missing": sorted(missing),
            },
        },
        "files": [
            file_fingerprint(item)
            for item in sorted(qx.values(), key=lambda entry: entry["path"])
            + sorted(shunt.values(), key=lambda entry: entry["path"])
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
    shunt, missing, modes = fetch_source_shuntrules(limit=limit)

    if limit is None:
        # 防御：来源异常大面积失败时不要删除已有文件
        if len(shunt) == 0:
            raise FetchError("ShuntRules：没有任何文件下载成功，保留现有文件并中止")
        if missing and len(missing) > len(shunt) * 0.2:
            raise FetchError(
                f"ShuntRules：失败 {len(missing)} / 成功 {len(shunt)}，超过 20%，"
                "为避免误删保留现有文件并中止"
            )
        if len(qx) == 0:
            raise FetchError("QuixoticHeart：没有任何文件下载成功，保留现有文件并中止")

    unified, unified_stats = build_unified(
        {**qx, **shunt}, CONFIG["unified"]["priority"]
    )

    totals = {
        "quixoticheart": sum(item["rules"] for item in qx.values()),
        "shuntrules": sum(item["rules"] for item in shunt.values()),
        "unified": sum(item["rules"] for item in unified.values()),
    }
    qx_dupes = sum(item.get("duplicates", 0) for item in qx.values())
    shunt_dupes = sum(item.get("duplicates", 0) for item in shunt.values())
    qx_unparsed = sum(item.get("unparsed", 0) for item in qx.values())
    shunt_unparsed = sum(item.get("unparsed", 0) for item in shunt.values())

    index_text = build_index(qx, shunt, unified, totals)
    conflicts_text = build_conflicts(
        unified_stats,
        {"duplicates": qx_dupes, "unparsed": qx_unparsed},
        {"duplicates": shunt_dupes, "unparsed": shunt_unparsed},
        missing,
        qx_failed,
    )
    manifest_text = build_manifest(qx, shunt, unified, missing, qx_failed, modes)

    summary = {
        "quixoticheart_files": len(qx),
        "quixoticheart_rules": totals["quixoticheart"],
        "quixoticheart_failed": len(qx_failed),
        "shuntrules_files": len(shunt),
        "shuntrules_rules": totals["shuntrules"],
        "shuntrules_direct": modes.get("direct", 0),
        "shuntrules_fallback": modes.get("fallback", 0),
        "shuntrules_missing": len(missing),
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
        path = repo_root / item["path"]
        if write_if_changed(path, item["text"]):
            changed.append(item["path"])
    for item in shunt.values():
        path = repo_root / item["path"]
        if write_if_changed(path, item["text"]):
            changed.append(item["path"])
    for item in unified.values():
        path = repo_root / item["path"]
        if write_if_changed(path, item["text"]):
            changed.append(item["path"])

    # 清理上游已删除的规则集（仅清理本次成功覆盖的目录；
    # --limit 调试模式或有文件下载失败时不做删除，避免误删）
    if limit is None:
        for subsection, entries, ext, source in (
            ("quixoticheart", qx, ".list", "quixoticheart"),
            ("shuntrules", shunt, ".lsr", "shuntrules"),
            ("unified", unified, CONFIG["unified"]["ext"], "unified"),
        ):
            if source == "unified" and (missing or qx_failed):
                continue
            directory = repo_root / CONFIG[subsection]["out"]
            keep = set(entries)
            if source == "shuntrules":
                keep |= {f"{name}{ext}" for name in missing}
            elif source == "quixoticheart":
                keep |= set(qx_failed)
            for removed in prune_stale(directory, keep, (ext,)):
                changed.append(os.path.relpath(removed, repo_root))

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
    parser = argparse.ArgumentParser(description="整合 QuixoticHeart/ShuntRules 的 Loon 规则")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 个文件（调试用）")
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
