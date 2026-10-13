"""Reproducible download and historical evaluation commands."""
import argparse
import json
from .data import download
from .pipeline import run

def main():
    parser=argparse.ArgumentParser(description="Danish spike probabilities and paper cap hedging")
    sub=parser.add_subparsers(dest="command",required=True)
    fetch=sub.add_parser("download",help="Fetch official 2025-10-01 to 2026-10-01 prices")
    fetch.add_argument("--data",default="data")
    backtest=sub.add_parser("run",help="Evaluate fixed windows and create a fresh report")
    backtest.add_argument("--data",default="data")
    backtest.add_argument("--out",default="reports/run")
    args=parser.parse_args()
    if args.command=="download":
        result=download(args.data)
        print(json.dumps({k:v for k,v in result.items() if k!="metadata"},indent=2))
    else:
        result=run(args.data,args.out)
        print(json.dumps({"areas":{a:{"selected":v["selected"],"strike":v["strike_eur_mwh"],
            "test":v["test"]["selected"]} for a,v in result["areas"].items()},
            "hedge":result["default_hedge"]},indent=2))

if __name__=="__main__":
    main()

