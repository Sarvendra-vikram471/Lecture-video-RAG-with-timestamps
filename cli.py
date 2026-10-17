import argparse

from lecture_rag.pipeline import answer, build_index

p = argparse.ArgumentParser(description="Lecture RAG with timestamp answers")
sub = p.add_subparsers(dest="cmd", required=True)
a = sub.add_parser("index", help="index a lecture URL or local file")
a.add_argument("source")
a.add_argument("--model", default="small", help="whisper size: tiny/base/small/medium")
q = sub.add_parser("ask", help="ask a question about an indexed lecture")
q.add_argument("video_id")
q.add_argument("question")
args = p.parse_args()

if args.cmd == "index":
    print("video_id:", build_index(args.source, args.model))
else:
    r = answer(args.video_id, args.question)
    print(r["answer"], f"\n\nJump to {r['timestamp']}: {r['url']}")
