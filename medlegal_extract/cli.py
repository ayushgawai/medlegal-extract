from __future__ import annotations
import argparse, json
from .eval import run_eval
from .pipeline import run_file


def main(argv=None):
    ap = argparse.ArgumentParser(prog="medlegal")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="extract one document"); r.add_argument("file")
    r.add_argument("--provider", default="stub", choices=["stub", "anthropic", "openai"])
    e = sub.add_parser("eval", help="evaluate on synthetic corpus"); e.add_argument("--n", type=int, default=200)
    e.add_argument("--seed", type=int, default=42)
    s = sub.add_parser("serve", help="run the API"); s.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        print(run_file(a.file, a.provider).model_dump_json(indent=2))
    elif a.cmd == "eval":
        print(json.dumps(run_eval(a.n, a.seed), indent=2))
    elif a.cmd == "serve":
        import uvicorn; uvicorn.run("medlegal_extract.app:app", port=a.port)


if __name__ == "__main__":
    main()
