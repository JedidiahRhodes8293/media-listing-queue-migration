from src.media_aggregation import Listing, ListingRequest, ProcessingJob, aggregate_listings, cutover_checklist


def test_aggregate_uses_scrape_content(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.media_aggregation._search",
        lambda request: [{"title": "One", "url": "https://source.test/one"}],
    )
    monkeypatch.setattr(
        "src.media_aggregation._request",
        lambda method, url, body: {"content": "scraped body"},
    )

    listings = aggregate_listings(ListingRequest(query="one", include_domains=["source.test"]))

    assert listings == [Listing("One", "https://source.test/one", "scraped body")]


def test_cutover_rejects_incomplete_creator_delivery() -> None:
    jobs = [
        ProcessingJob("https://source.test/one", {"title": "One", "body": "usable"}),
        ProcessingJob("https://source.test/two", {"title": "Two", "body": ""}),
    ]
    assert cutover_checklist(jobs) is False
    assert cutover_checklist([ProcessingJob("https://source.test/one", {"title": "One", "body": "usable"})]) is True
