from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

from .segments import build_meal_segments_from_root
from .bio import merge_segments_with_bio
from .train import train_random_forest
from .evaluate import eval_with_nulls

def main():
    ap = argparse.ArgumentParser(prog="cgmacros-pipeline", description="CGMacros data processing CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("extract", help="Extract meal segments from CGMacros directory")
    p1.add_argument("--root", default=".", type=Path)
    p1.add_argument("--out", default=Path("all_users_all_meal_segments.csv"), type=Path)

    p2 = sub.add_parser("merge-bio", help="Merge segments with bio.csv")
    p2.add_argument("--segments", default=Path("all_users_all_meal_segments.csv"), type=Path)
    p2.add_argument("--bio", default=Path("bio.csv"), type=Path)
    p2.add_argument("--out", default=Path("all_meal_segments_with_bio.csv"), type=Path)

    p3 = sub.add_parser("train", help="Train RF multi-output model")
    p3.add_argument("--data", default=Path("all_meal_segments_with_bio.csv"), type=Path)
    p3.add_argument("--out", default=Path("ml_outputs_mlcurve_rf"), type=Path)

    p4 = sub.add_parser("eval", help="Evaluate model with nulls")
    p4.add_argument("--data", default=Path("all_meal_segments_with_bio.csv"), type=Path)
    p4.add_argument("--model", default=Path("ml_outputs_mlcurve_rf/model_multioutput.pkl"), type=Path)
    p4.add_argument("--out", default=Path("ml_outputs_mlcurve_eval"), type=Path)

    p5 = sub.add_parser("pipeline", help="Run full pipeline: extract → merge-bio → train → eval")
    p5.add_argument("--root", default=".", type=Path)
    p5.add_argument("--bio", default=Path("bio.csv"), type=Path)
    p5.add_argument("--workdir", default=Path("."), type=Path)

    args = ap.parse_args()

    if args.cmd == "extract":
        segs = build_meal_segments_from_root(str(args.root))
        combined = pd.concat(segs, ignore_index=True) if segs else pd.DataFrame()
        combined.to_csv(args.out, index=False)
        print(f"Wrote {args.out} with {len(combined)} rows")
    elif args.cmd == "merge-bio":
        out = merge_segments_with_bio(args.segments, args.bio, args.out)
        print("Merged →", out)
    elif args.cmd == "train":
        info = train_random_forest(args.data, args.out)
        print("Training summary:", info)
    elif args.cmd == "eval":
        info = eval_with_nulls(args.data, args.model, args.out)
        print("Eval summary:", info)
    elif args.cmd == "pipeline":
        work = args.workdir
        seg_csv = work / "all_users_all_meal_segments.csv"
        segs = build_meal_segments_from_root(str(args.root))
        pd.concat(segs, ignore_index=True).to_csv(seg_csv, index=False)

        merged_csv = work / "all_meal_segments_with_bio.csv"
        merge_segments_with_bio(seg_csv, args.bio, merged_csv)

        out_dir = work / "ml_outputs_mlcurve_rf"
        train_random_forest(merged_csv, out_dir)

        eval_dir = work / "ml_outputs_mlcurve_eval"
        eval_with_nulls(merged_csv, out_dir / "model_multioutput.pkl", eval_dir)
        print("Pipeline completed.")
