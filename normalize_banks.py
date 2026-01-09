import re
from pathlib import Path
import shutil
import argparse

# A-타입 통일 대상 번호
MARKERS = ["①", "②", "③", "④", "⑤"]

# explanation 템플릿 리터럴: explanation: ` ... `
TPL_EXPL_RE = re.compile(r'(explanation\s*:\s*`)([\s\S]*?)(`)', re.M)

# explanation 문자열: explanation: " ... "
# (JS 문자열은 줄바꿈을 허용하지 않으므로, 실무적으로는 대부분 한 줄이지만, 그래도 지원)
STR_EXPL_RE = re.compile(r'(explanation\s*:\s*")([^"]*)(")', re.M)

MARKER_ONLY_RE = re.compile(r"^(?P<num>[①②③④⑤])\s*(\((?:○|×)\))?\s*$")

def unify_a_type_multiline(expl: str) -> str:
    """
    explanation 텍스트(멀티라인)를 A-타입으로 통일:
    - '① (×)' 같은 '마커만 있는 줄'을 발견하면
      다음 '비어있지 않은 줄'을 같은 줄로 합친다.
    """
    lines = expl.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if any(stripped.startswith(m) for m in MARKERS) and MARKER_ONLY_RE.match(stripped):
            # 다음 non-empty 라인을 찾아 합치기
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines):
                merged = stripped + " " + lines[j].strip()
                out.append(merged)
                i = j + 1
                continue

        out.append(line)
        i += 1

    return "\n".join(out).rstrip()

def process_js_file(path: Path) -> bool:
    """
    파일을 정규화하고 변경되면 True 반환.
    """
    src = path.read_text(encoding="utf-8")

    def tpl_repl(m):
        prefix, body, suffix = m.group(1), m.group(2), m.group(3)
        fixed = unify_a_type_multiline(body)
        return prefix + fixed + suffix

    new = TPL_EXPL_RE.sub(tpl_repl, src)

    # 문자열 explanation도 일단 지원(대개 한 줄이라 큰 변화 없을 수 있음)
    # 멀티라인이 아니라면 A-타입 통일 효과가 거의 없음.
    def str_repl(m):
        prefix, body, suffix = m.group(1), m.group(2), m.group(3)
        # 문자열은 원래 개행이 없으니, "① (×) " 패턴이 "① (×)"로만 존재하면 합칠 게 없음
        # 그래도 안전하게 공백 정리 정도만 수행
        fixed = re.sub(r"\s{2,}", " ", body).strip()
        return prefix + fixed + suffix

    new = STR_EXPL_RE.sub(str_repl, new)

    if new != src:
        # 백업 생성
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(new, encoding="utf-8")
        return True

    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="banks", help="bank_*.js가 들어있는 폴더 (기본: banks)")
    parser.add_argument("--pattern", default="bank_*.js", help="대상 파일 패턴 (기본: bank_*.js)")
    args = parser.parse_args()

    target_dir = Path(args.dir)
    if not target_dir.exists():
        raise SystemExit(f"[ERR] 폴더가 없습니다: {target_dir.resolve()}")

    files = sorted(target_dir.glob(args.pattern))
    if not files:
        raise SystemExit(f"[ERR] 대상 파일이 없습니다: {target_dir.resolve()}/{args.pattern}")

    changed = 0
    for f in files:
        if process_js_file(f):
            changed += 1
            print(f"[OK] normalized: {f}")
        else:
            print(f"[SKIP] no change:  {f}")

    print(f"\nDone. changed={changed}, total={len(files)}")
    print("※ 변경된 파일은 .bak 백업이 함께 생성됩니다(최초 1회).")

if __name__ == "__main__":
    main()