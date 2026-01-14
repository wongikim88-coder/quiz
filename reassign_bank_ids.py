# reassign_bank_ids.py (patched)
# 목적: bank 파일들의 id를 자동 재부여하되,
#      "파일 순서"가 아니라 "파일명에 포함된 블록 번호"로 대역을 고정하여
#      중간에 새 파일을 추가해도 기존 id 대역이 밀리지 않게 한다.
#
# 파일명 규칙(필수): bank_###_something.js  (### = 3자리 숫자)
# 예: bank_010_civil.js, bank_020_civil_2.js
#
# 권장 실행:
#   1) 미리보기:
#      python reassign_bank_ids.py --dir . --glob "bank_*.js" --mode block --block-size 10000 --start 10000 --dry-run
#   2) 실제 적용:
#      python reassign_bank_ids.py --dir . --glob "bank_*.js" --mode block --block-size 10000 --start 10000
#
# 옵션:
#   --mode block  : 파일명 블록번호 기반으로 대역 고정(추천)
#   --mode global : 모든 파일 통틀어 연속 부여
#
# 백업:
#   원본 파일은 동일 경로에 *.bak 로 1회 백업 생성(이미 존재하면 덮어쓰지 않음)

import argparse
import glob
import os
import re
import shutil
from typing import List, Tuple, Optional

# "id: 123," 또는 "id: 123\n" 형태만 치환
ID_PATTERN = re.compile(r'(\bid\s*:\s*)(\d+)(\s*[,\n])')

# bank_010_xxx.js -> 10
FILE_BLOCK_PATTERN = re.compile(r'^bank_(\d{3})_.*\.js$', re.IGNORECASE)

def find_files(base_dir: str, pattern: str) -> List[str]:
    files = glob.glob(os.path.join(base_dir, pattern))
    files = [f for f in files if os.path.isfile(f)]
    files.sort(key=lambda p: os.path.basename(p).lower())
    return files

def parse_block_no(filename: str) -> Optional[int]:
    m = FILE_BLOCK_PATTERN.match(filename)
    if not m:
        return None
    return int(m.group(1))

def reassign_ids_in_text(text: str, start_id: int) -> Tuple[str, int, List[Tuple[int, int]]]:
    current = start_id
    changes: List[Tuple[int, int]] = []

    def repl(m: re.Match) -> str:
        nonlocal current, changes
        prefix, old_id_str, suffix = m.group(1), m.group(2), m.group(3)
        old_id = int(old_id_str)
        new_id = current
        current += 1
        changes.append((old_id, new_id))
        return f"{prefix}{new_id}{suffix}"

    new_text, _ = ID_PATTERN.subn(repl, text)
    return new_text, current, changes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".", help="bank 파일 디렉토리")
    ap.add_argument("--glob", default="bank_*.js", help='대상 파일 패턴 (추천: "bank_*.js")')
    ap.add_argument("--mode", choices=["block", "global"], default="block")
    ap.add_argument("--block-size", type=int, default=10000, help="block 모드에서 블록 크기")
    ap.add_argument("--start", type=int, default=10000, help="시작 id (global 시작 또는 block 공식에 사용)")
    ap.add_argument("--dry-run", action="store_true", help="파일은 수정하지 않고 변경 요약만 출력")
    args = ap.parse_args()

    files = find_files(args.dir, args.glob)
    if not files:
        raise SystemExit(f"대상 파일이 없습니다: dir={args.dir}, glob={args.glob}")

    global_next = args.start

    print(f"Mode={args.mode}, Files={len(files)}")
    for path in files:
        base = os.path.basename(path)

        with open(path, "r", encoding="utf-8") as f:
            original = f.read()

        if args.mode == "block":
            block_no = parse_block_no(base)
            if block_no is None:
                raise SystemExit(
                    f"파일명이 규칙에 맞지 않습니다: {base}\n"
                    f"필수 규칙: bank_###_something.js (예: bank_010_civil.js)"
                )

            # 안정형 대역 공식:
            # start=10000, block-size=10000, block_no=10 -> 10000 + (10-1)*10000 = 100000
            file_start = args.start + (block_no - 1) * args.block_size
        else:
            file_start = global_next

        new_text, next_id, changes = reassign_ids_in_text(original, file_start)

        if args.mode == "global":
            global_next = next_id

        print(f"\n[{base}] start={file_start}, changed={len(changes)}")
        if changes:
            head = changes[:3]
            tail = changes[-3:] if len(changes) > 3 else []
            print("  sample(head): " + ", ".join([f"{o}->{n}" for o, n in head]))
            if tail:
                print("  sample(tail): " + ", ".join([f"{o}->{n}" for o, n in tail]))

        if args.dry_run:
            continue

        bak_path = path + ".bak"
        if not os.path.exists(bak_path):
            shutil.copy2(path, bak_path)

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_text)

    print("\nDone.")
    if not args.dry_run:
        print("원본 백업: *.bak")

if __name__ == "__main__":
    main()
