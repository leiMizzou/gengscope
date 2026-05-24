from __future__ import annotations

import argparse
import os
import sys
import time


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the GengScope background job worker.")
    parser.add_argument(
        "--database-url",
        help="Database URL. Defaults to DATABASE_URL or sqlite:///./gengscope_api.db.",
    )
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Seconds to sleep between empty polls.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    parser.add_argument("--disable-schedules", action="store_true", help="Do not enqueue due scheduled jobs before polling.")
    parser.add_argument(
        "--recover-stale-after",
        type=float,
        default=0.0,
        help="Seconds after which a running job is treated as stale. Disabled by default.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    from gengscope_api.db.session import SessionLocal, init_db
    from gengscope_api.services.jobs import enqueue_due_scheduled_jobs, process_next_job, requeue_stale_jobs

    init_db()

    while True:
        try:
            with SessionLocal() as db:
                if args.recover_stale_after > 0:
                    requeue_stale_jobs(db, stale_after_seconds=args.recover_stale_after)
                if not args.disable_schedules:
                    enqueue_due_scheduled_jobs(db)
                result = process_next_job(db)
        except Exception as exc:
            if args.once:
                raise
            print(f"gengscope-worker error: {exc}", file=sys.stderr, flush=True)
            time.sleep(args.poll_interval)
            continue
        if args.once:
            return 0
        if result is None:
            time.sleep(args.poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
