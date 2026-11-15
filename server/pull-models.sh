#!/usr/bin/env bash
# 4411.site · 模型工作台每日同步（供宝塔「计划任务 → Shell 脚本」调用）
#
# 设计原则：只覆盖白名单 5 个文件；全部下载 + 校验通过才覆盖；
#           任何一步失败都保留线上原样并写日志，绝不把半成品推到公网。
# 可按需用环境变量覆盖：OWNER / REPO / BRANCH / DEST / BACKUP / LOG
set -Eeuo pipefail

OWNER="${OWNER:-niefree1110-ship-it}"
REPO="${REPO:-4411-site-models}"
BRANCH="${BRANCH:-main}"
DEST="${DEST:-/www/wwwroot/4411.site/models}"
BACKUP="${BACKUP:-/www/backup/4411-models}"
LOG="${LOG:-/var/log/4411-pull.log}"
FILES=(index.html aihot-data.js leaderboard.html resets.html free-tokens.html)

log() { printf '[%s] %s\n' "$(date '+%F %T %z')" "$*" | tee -a "$LOG"; }
die() { log "失败：$*（线上保持原样）"; exit 1; }

BK=""
rollback() {
  [ -n "$BK" ] || return 0
  log "回滚到 $BK"
  for f in "${FILES[@]}"; do
    if [ -f "${BK}/${f}" ]; then cp -p "${BK}/${f}" "${DEST}/${f}" || true; fi
  done
}

mkdir -p "$DEST" "$BACKUP" "$(dirname "$LOG")" || die "目录不可写"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 主源 raw 无长缓存，保证拿到当天版本；jsDelivr 双节点作备源（国内服务器可达性更好）
fetch_one() {
  local f="$1" ts src
  ts="$(date +%s)"
  local urls=(
    "https://raw.githubusercontent.com/${OWNER}/${REPO}/${BRANCH}/models/${f}?v=${ts}"
    "https://cdn.jsdelivr.net/gh/${OWNER}/${REPO}@${BRANCH}/models/${f}?v=${ts}"
    "https://fastly.jsdelivr.net/gh/${OWNER}/${REPO}@${BRANCH}/models/${f}?v=${ts}"
  )
  for u in "${urls[@]}"; do
    src="$(printf '%s' "$u" | cut -d/ -f3)"
    if curl -fsSL --connect-timeout 10 --max-time 60 "$u" -o "${TMP}/${f}" && [ -s "${TMP}/${f}" ]; then
      log "  下载 OK  ${src} → ${f}  ($(wc -c < "${TMP}/${f}") B)"
      return 0
    fi
  done
  return 1
}

log "开始同步  ${OWNER}/${REPO}@${BRANCH} → ${DEST}"
for f in "${FILES[@]}"; do
  fetch_one "$f" || die "下载失败：$f"
done

# 完整性校验：挡住 404 页 / CDN 错误页 / 被截断的半成品
for f in "${FILES[@]}"; do
  [ "$(wc -c < "${TMP}/${f}")" -gt 1024 ] || die "文件过小：$f"
done
grep -q 'const MODELS = \[' "${TMP}/index.html" || die "index.html 缺少 MODELS 数组"
grep -q 'const GENERATED = "20' "${TMP}/index.html" || die "index.html 缺少 GENERATED 时间戳"
grep -q 'window.AIHOT = ' "${TMP}/aihot-data.js" || die "aihot-data.js 缺少 window.AIHOT"
for f in leaderboard.html resets.html free-tokens.html; do
  grep -qi '<html' "${TMP}/${f}" || die "$f 不是完整 HTML"
done

# 不倒退：备源 CDN 可能吐旧缓存，绝不能用旧快照覆盖线上较新的数据
NEW_STAMP="$(grep -o 'const GENERATED = "[^"]*' "${TMP}/index.html" | cut -d'"' -f2)"
OLD_STAMP=""
if [ -f "${DEST}/index.html" ]; then
  OLD_STAMP="$(grep -o 'const GENERATED = "[^"]*' "${DEST}/index.html" | cut -d'"' -f2 || true)"
fi
if [ -n "$OLD_STAMP" ] && [[ "$NEW_STAMP" < "$OLD_STAMP" ]]; then
  die "下载快照 ${NEW_STAMP} 早于线上 ${OLD_STAMP}，疑似 CDN 旧缓存，拒绝倒退"
fi

# 与线上完全一致就什么都不动（保住 mtime，也少一次无谓写入）
changed=0
for f in "${FILES[@]}"; do
  if ! cmp -s "${TMP}/${f}" "${DEST}/${f}"; then changed=1; break; fi
done
if [ "$changed" -eq 0 ]; then
  log "与线上一致，无需更新"
  exit 0
fi

BK="${BACKUP}/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BK" || die "无法创建备份目录 $BK"
for f in "${FILES[@]}"; do
  if [ -f "${DEST}/${f}" ]; then cp -p "${DEST}/${f}" "${BK}/${f}"; fi
done

# 先写 .new 再 mv，避免读者撞上半截文件
for f in "${FILES[@]}"; do
  install -m 644 "${TMP}/${f}" "${DEST}/${f}.new" || { rollback; die "写入失败：$f"; }
  mv -f "${DEST}/${f}.new" "${DEST}/${f}" || { rollback; die "覆盖失败：$f"; }
done
for f in "${FILES[@]}"; do
  [ -s "${DEST}/${f}" ] || { rollback; die "覆盖后文件为空：$f"; }
done

# 只保留最近 7 份备份
ls -1dt "${BACKUP}"/20* 2>/dev/null | tail -n +8 | xargs -r rm -rf || true

log "更新完成 · 快照 ${NEW_STAMP} · 备份 ${BK}"
