#!/bin/bash
# CLAUDE.md와 AGENTS.md가 같은 파일(하드링크)인지 확인.
# inode가 다르면 하드링크를 재생성한다.
# pre-commit 훅에서 자동 실행됨.

cd "$(git rev-parse --show-toplevel)" || exit 1

CLAUDE_INODE=$(stat -c %i CLAUDE.md 2>/dev/null)
AGENTS_INODE=$(stat -c %i AGENTS.md 2>/dev/null)

if [ "$CLAUDE_INODE" != "$AGENTS_INODE" ]; then
    rm -f AGENTS.md
    cmd //c "mklink /H AGENTS.md CLAUDE.md" > /dev/null 2>&1
    # Git staging에 반영
    git add AGENTS.md
    echo "[sync] AGENTS.md 하드링크 복구됨"
fi
