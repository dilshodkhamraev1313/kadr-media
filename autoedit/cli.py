# ============================================================
#  Buyruq qatori (CLI) — montaj dvigatelini terminaldan ishlatish
#  Misollar:
#    python3 -m autoedit styles
#    python3 -m autoedit check
#    python3 -m autoedit analyze --ref namuna.mp4
#    python3 -m autoedit edit --inputs a.mp4 b.mp4 --style trend_fast \
#            --music fon.mp3 --out tayyor.mp4
#    python3 -m autoedit edit --inputs a.mp4 --ref namuna.mp4 --out tayyor.mp4
# ============================================================

import argparse
import json
import sys

from .styles import list_styles, get_style, derived_from_reference
from .engine import auto_edit, EditOptions
from .ffmpeg_utils import tools_status
from .analyze import analyze_reference


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="autoedit", description="Kadr Media — avtomatik montaj dvigateli"
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("styles", help="Mavjud montaj stillari")
    sub.add_parser("check", help="ffmpeg/whisper bor-yo'qligini tekshirish")

    pa = sub.add_parser("analyze", help="Referens videoni tahlil qilish")
    pa.add_argument("--ref", required=True, help="Referens video yo'li")

    pe = sub.add_parser("edit", help="Avtomatik montaj qilish")
    pe.add_argument("--inputs", nargs="+", required=True, help="Isxodnik videolar")
    pe.add_argument("--style", default="trend_fast", help="Stil kaliti")
    pe.add_argument("--ref", help="Referens video (stil undan olinadi)")
    pe.add_argument("--music", help="Fon musiqa fayli")
    pe.add_argument("--out", required=True, help="Tayyor video yo'li")
    pe.add_argument("--lang", default="uz", help="Subtitr tili (standart: uz)")
    pe.add_argument("--model", default="small", help="Whisper model o'lchami")

    args = parser.parse_args(argv)

    if args.cmd == "styles":
        print(json.dumps(list_styles(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "check":
        st = tools_status()
        print(json.dumps(st, ensure_ascii=False, indent=2))
        if not st["ready"]:
            print("\n⚠️  ffmpeg/ffprobe yo'q. O'rnating: apt install ffmpeg "
                  "(Ubuntu) yoki brew install ffmpeg (Mac).", file=sys.stderr)
        return 0 if st["ready"] else 1

    if args.cmd == "analyze":
        analysis = analyze_reference(args.ref)
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "edit":
        if args.ref:
            analysis = analyze_reference(args.ref)
            style = derived_from_reference(analysis, base=args.style)
            print("Referensdan olingan stil:",
                  json.dumps(analysis, ensure_ascii=False))
        else:
            style = get_style(args.style)

        opts = EditOptions(
            inputs=args.inputs, style=style, output=args.out,
            music=args.music, language=args.lang, whisper_model=args.model,
        )
        result = auto_edit(opts, progress=lambda m: print("•", m))
        print(f"\n✅ Tayyor: {result.output}")
        print(f"   Davomiyligi: {result.duration}s, kadrlar: {result.segments}, "
              f"subtitr: {'ha' if result.subtitled else 'yoq'}")
        for w in result.warnings:
            print(f"   ⚠️  {w}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
