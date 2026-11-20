import argparse

from .media_aggregation import ListingRequest, aggregate_listings, jobs_for_creator, publish_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate media listings and queue creator processing jobs.")
    parser.add_argument("query")
    parser.add_argument("--domain", action="append", required=True)
    args = parser.parse_args()
    request = ListingRequest(query=args.query, include_domains=args.domain)
    jobs = jobs_for_creator(aggregate_listings(request))
    print(f"queued {publish_jobs(jobs)} media processing jobs")


if __name__ == "__main__":
    main()
