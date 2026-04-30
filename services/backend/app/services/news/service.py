import hashlib
import html
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.asset import Asset
from app.models.health import SystemHealthEvent
from app.models.news import ExtractedEvent, NewsArticle
from app.services.events.extraction import event_extraction_service
from app.utils.time import utcnow

settings = get_settings()


class NewsService:
    def list_articles(self, db: Session) -> list[NewsArticle]:
        return list(
            db.scalars(
                select(NewsArticle)
                .where(NewsArticle.provider_type != "system", ~NewsArticle.url.like("https://local.demo/%"))
                .order_by(desc(NewsArticle.published_at))
                .limit(100)
            )
        )

    def list_events(self, db: Session) -> list[ExtractedEvent]:
        filtered: list[ExtractedEvent] = []
        events = list(db.scalars(select(ExtractedEvent).order_by(desc(ExtractedEvent.created_at)).limit(150)))
        for event in events:
            if not event.news_article_id:
                filtered.append(event)
            else:
                article = db.get(NewsArticle, event.news_article_id)
                if article and article.provider_type != "system" and not article.url.startswith("https://local.demo/"):
                    filtered.append(event)
            if len(filtered) >= 100:
                break
        return filtered

    def latest_refresh_diagnostics(self, db: Session) -> dict:
        event = db.scalar(
            select(SystemHealthEvent)
            .where(SystemHealthEvent.component == "news.rss_refresh")
            .order_by(desc(SystemHealthEvent.observed_at))
            .limit(1)
        )
        if event is None:
            return {
                "message": "No RSS refresh has been recorded yet.",
                "run_type": "none",
                "observed_at": None,
                "articles_added": 0,
                "feeds_checked": 0,
                "feeds_failed": 0,
                "duplicates_skipped": 0,
                "date_skipped": 0,
                "latest_article_id": None,
                "cutoff": utcnow().isoformat(),
                "latest_seen_published_at": None,
                "force_refresh": False,
                "last_successful_fetch_time": None,
                "errors": [],
                "feed_reports": [],
            }
        metadata = event.metadata_json or {}
        return {
            "message": event.message,
            "run_type": metadata.get("run_type", "manual"),
            "observed_at": event.observed_at.isoformat(),
            "articles_added": metadata.get("articles_added", 0),
            "feeds_checked": metadata.get("feeds_checked", 0),
            "feeds_failed": metadata.get("feeds_failed", 0),
            "duplicates_skipped": metadata.get("duplicates_skipped", 0),
            "date_skipped": metadata.get("date_skipped", 0),
            "latest_article_id": metadata.get("latest_article_id"),
            "cutoff": metadata.get("cutoff", event.observed_at.isoformat()),
            "latest_seen_published_at": metadata.get("latest_seen_published_at"),
            "force_refresh": metadata.get("force_refresh", False),
            "last_successful_fetch_time": metadata.get("last_successful_fetch_time"),
            "errors": metadata.get("errors", []),
            "feed_reports": metadata.get("feed_reports", []),
        }

    def refresh_latest_news(
        self,
        db: Session,
        *,
        force_refresh: bool = False,
        backfill_hours: int | None = None,
        run_type: str = "manual",
    ) -> dict:
        refresh_started_at = utcnow()
        feed_urls = self._build_feed_urls(db)
        tracked_assets = list(db.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.symbol)))
        last_successful_refresh = self._last_successful_refresh(db)
        checkpoint = self._last_refresh_checkpoint(db)
        if force_refresh:
            cutoff = refresh_started_at - timedelta(hours=backfill_hours or settings.news_force_backfill_hours)
        else:
            if checkpoint:
                checkpoint_cutoff = checkpoint - timedelta(minutes=settings.news_refresh_overlap_minutes)
                rolling_cutoff = refresh_started_at - timedelta(hours=settings.news_incremental_backfill_hours)
                # RSS feeds can expose delayed items whose publication time is older than the newest item seen.
                # Keep a rolling lookback and let URL/dedupe guards prevent re-imports.
                cutoff = min(checkpoint_cutoff, rolling_cutoff)
            else:
                cutoff = refresh_started_at - timedelta(hours=settings.news_initial_lookback_hours)

        recent_articles = list(
            db.scalars(
                select(NewsArticle)
                .where(NewsArticle.published_at >= cutoff - timedelta(days=7))
                .order_by(desc(NewsArticle.published_at))
                .limit(500)
            )
        )
        existing_urls = {article.url for article in recent_articles}
        existing_dedupe_keys = {article.dedupe_key for article in recent_articles if article.dedupe_key}

        articles_added = 0
        feeds_failed = 0
        duplicates_skipped = 0
        date_skipped = 0
        latest_article_id = None
        errors: list[str] = []
        feed_reports: list[dict] = []
        latest_seen_published_at: datetime | None = checkpoint

        for feed_url in feed_urls:
            feed_report = {
                "feed_url": feed_url,
                "feed_label": self._feed_label(feed_url),
                "status": "ok",
                "fetched_count": 0,
                "added_count": 0,
                "duplicate_count": 0,
                "date_skipped_count": 0,
                "parse_error_count": 0,
                "sample_titles": [],
                "latest_seen_published_at": None,
                "error": None,
            }
            try:
                document = self._fetch_feed(feed_url)
                entries = self._parse_feed(document)
            except Exception as exc:
                feeds_failed += 1
                message = f"{feed_url}: {exc}"
                errors.append(message)
                feed_report["status"] = "error"
                feed_report["error"] = str(exc)
                feed_reports.append(feed_report)
                continue

            feed_report["fetched_count"] = len(entries)
            feed_report["sample_titles"] = [entry["title"] for entry in entries[:3] if entry.get("title")]
            for entry in entries[: settings.news_feed_items_limit]:
                published_at = self._ensure_utc(entry["published_at"] or refresh_started_at)
                latest_seen_published_at = max(
                    [value for value in [latest_seen_published_at, published_at] if value is not None],
                    default=published_at,
                )
                current_feed_latest = feed_report["latest_seen_published_at"]
                feed_report["latest_seen_published_at"] = max(
                    [value for value in [current_feed_latest, published_at] if value is not None],
                    default=published_at,
                )
                if not force_refresh and published_at <= cutoff:
                    date_skipped += 1
                    feed_report["date_skipped_count"] += 1
                    continue

                url = self._prepare_url(entry["url"], entry["guid"])
                dedupe_key = self._build_dedupe_key(entry)
                if not url or url in existing_urls or dedupe_key in existing_dedupe_keys:
                    duplicates_skipped += 1
                    feed_report["duplicate_count"] += 1
                    continue

                affected_symbols = self._match_symbols(entry["title"], entry["summary"], tracked_assets)
                sentiment = self._infer_sentiment(entry["title"], entry["summary"])
                event_type = self._infer_event_type(entry["title"], entry["summary"])
                impact_score = self._infer_impact_score(event_type, affected_symbols)

                article = NewsArticle(
                    title=self._truncate(entry["title"], 255),
                    source=self._truncate(entry["source"], 120),
                    url=url,
                    published_at=published_at,
                    summary=entry["summary"],
                    sentiment=sentiment,
                    impact_score=impact_score,
                    affected_symbols=affected_symbols,
                    provider_type="rss",
                    model_name="rss-heuristic",
                    dedupe_key=dedupe_key,
                    analysis_metadata={
                        "feed_url": feed_url,
                        "guid": entry["guid"],
                        "raw_url": entry["url"],
                        "cutoff": cutoff.isoformat(),
                    },
                )
                db.add(article)
                db.flush()

                db.add(
                    ExtractedEvent(
                        news_article_id=article.id,
                        event_type=event_type,
                        symbol=affected_symbols[0] if affected_symbols else None,
                        confidence=0.74 if affected_symbols else 0.58,
                        impact_score=impact_score,
                        summary=entry["summary"] or article.title,
                        metadata_json={"source": article.source, "rss": True},
                    )
                )
                db.flush()

                existing_urls.add(url)
                existing_dedupe_keys.add(dedupe_key)
                latest_article_id = article.id
                articles_added += 1
                feed_report["added_count"] += 1

            if feed_report["added_count"] == 0 and feed_report["fetched_count"] == 0:
                feed_report["status"] = "warn"
            elif feed_report["added_count"] == 0 and feed_report["duplicate_count"]:
                feed_report["status"] = "warn"
            elif feed_report["added_count"] == 0 and feed_report["date_skipped_count"]:
                feed_report["status"] = "stale"
            feed_reports.append(feed_report)

        successful_feeds = len(feed_urls) - feeds_failed
        status = "ok"
        if successful_feeds <= 0:
            status = "error"
        elif feeds_failed:
            status = "warn"
        elif articles_added == 0:
            status = "warn"

        message = self._refresh_message(
            articles_added=articles_added,
            feeds_checked=len(feed_urls),
            cutoff=cutoff,
            duplicates_skipped=duplicates_skipped,
            date_skipped=date_skipped,
            feeds_failed=feeds_failed,
            force_refresh=force_refresh,
        )

        serialized_feed_reports = [
            {
                **report,
                "latest_seen_published_at": report["latest_seen_published_at"].isoformat() if report["latest_seen_published_at"] else None,
            }
            for report in feed_reports
        ]

        db.add(
            SystemHealthEvent(
                component="news.rss_refresh",
                status=status,
                message=message,
                metadata_json={
                    "run_type": run_type,
                    "articles_added": articles_added,
                    "feeds_checked": len(feed_urls),
                    "feeds_failed": feeds_failed,
                    "duplicates_skipped": duplicates_skipped,
                    "date_skipped": date_skipped,
                    "latest_article_id": latest_article_id,
                    "cutoff": cutoff.isoformat(),
                    "checkpoint": checkpoint.isoformat() if checkpoint else None,
                    "rolling_backfill_hours": settings.news_incremental_backfill_hours if not force_refresh else backfill_hours or settings.news_force_backfill_hours,
                    "latest_seen_published_at": latest_seen_published_at.isoformat() if latest_seen_published_at else None,
                    "last_successful_fetch_time": last_successful_refresh.isoformat() if last_successful_refresh else None,
                    "force_refresh": force_refresh,
                    "feed_reports": serialized_feed_reports,
                    "errors": errors[:5],
                },
                observed_at=refresh_started_at,
            )
        )

        return {
            "message": message,
            "run_type": run_type,
            "observed_at": refresh_started_at.isoformat(),
            "articles_added": articles_added,
            "feeds_checked": len(feed_urls),
            "feeds_failed": feeds_failed,
            "duplicates_skipped": duplicates_skipped,
            "date_skipped": date_skipped,
            "latest_article_id": latest_article_id,
            "cutoff": cutoff.isoformat(),
            "checkpoint": checkpoint.isoformat() if checkpoint else None,
            "rolling_backfill_hours": settings.news_incremental_backfill_hours if not force_refresh else backfill_hours or settings.news_force_backfill_hours,
            "latest_seen_published_at": latest_seen_published_at.isoformat() if latest_seen_published_at else None,
            "force_refresh": force_refresh,
            "last_successful_fetch_time": last_successful_refresh.isoformat() if last_successful_refresh else None,
            "feed_reports": serialized_feed_reports,
            "errors": errors[:5],
        }

    def _last_successful_refresh(self, db: Session) -> datetime | None:
        event = db.scalar(
            select(SystemHealthEvent)
            .where(SystemHealthEvent.component == "news.rss_refresh", SystemHealthEvent.status.in_(["ok", "warn"]))
            .order_by(desc(SystemHealthEvent.observed_at))
            .limit(1)
        )
        return self._ensure_utc(event.observed_at) if event else None

    def _last_refresh_checkpoint(self, db: Session) -> datetime | None:
        event = db.scalar(
            select(SystemHealthEvent)
            .where(SystemHealthEvent.component == "news.rss_refresh", SystemHealthEvent.status.in_(["ok", "warn"]))
            .order_by(desc(SystemHealthEvent.observed_at))
            .limit(1)
        )
        checkpoint = None
        if event:
            metadata = event.metadata_json or {}
            checkpoint = metadata.get("latest_seen_published_at") or metadata.get("cutoff")
            if checkpoint:
                try:
                    return self._ensure_utc(datetime.fromisoformat(str(checkpoint).replace("Z", "+00:00")))
                except Exception:
                    checkpoint = None

        latest_article = db.scalar(
            select(NewsArticle)
            .where(NewsArticle.provider_type != "system", ~NewsArticle.url.like("https://local.demo/%"))
            .order_by(desc(NewsArticle.published_at))
            .limit(1)
        )
        return self._ensure_utc(latest_article.published_at) if latest_article else None

    def _build_feed_urls(self, db: Session) -> list[str]:
        urls = list(settings.news_rss_feeds)
        tracked_assets = list(
            db.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.symbol).limit(settings.news_symbol_feed_limit))
        )

        for asset in tracked_assets:
            query_parts = [asset.symbol.split(".")[0], f'"{asset.name}"']
            if asset.asset_type == "etf":
                query_parts.append("ETF")
            else:
                query_parts.append("stock")
            query_parts.append("when:2d")
            query = quote_plus(" OR ".join(part for part in query_parts if part))
            urls.append(f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en")

        return list(dict.fromkeys(urls))

    def _fetch_feed(self, feed_url: str) -> str:
        response = httpx.get(feed_url, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        return response.text

    def _feed_label(self, feed_url: str) -> str:
        parsed = urlparse(feed_url)
        host = parsed.netloc or "rss"
        if "news.google.com" in host and "search" in parsed.path:
            return "Google News search"
        return host

    def _refresh_message(
        self,
        *,
        articles_added: int,
        feeds_checked: int,
        cutoff: datetime,
        duplicates_skipped: int,
        date_skipped: int,
        feeds_failed: int,
        force_refresh: bool,
    ) -> str:
        if articles_added:
            message = (
                f"Fetched {articles_added} new RSS article{'s' if articles_added != 1 else ''} "
                f"from {feeds_checked} feed{'s' if feeds_checked != 1 else ''} since {cutoff.isoformat()}."
            )
        else:
            message = (
                f"No fresh RSS articles were imported from {feeds_checked} feed{'s' if feeds_checked != 1 else ''}. "
                f"{duplicates_skipped} duplicate item{'s' if duplicates_skipped != 1 else ''} and "
                f"{date_skipped} older item{'s' if date_skipped != 1 else ''} were skipped since {cutoff.isoformat()}."
            )
            if not force_refresh:
                message = (
                    f"{message} Latest refresh keeps a rolling {settings.news_incremental_backfill_hours}h overlap "
                    "to catch delayed RSS items; use force refresh or backfill for a wider re-read."
                )
        if feeds_failed:
            message = f"{message} {feeds_failed} feed{'s' if feeds_failed != 1 else ''} failed."
        return message

    def _parse_feed(self, document: str) -> list[dict]:
        root = ElementTree.fromstring(document)
        entries = []
        entry_nodes = root.findall(".//item") or root.findall(".//{*}entry")

        for node in entry_nodes:
            title = self._clean_text(self._child_text(node, ["title"]))
            if not title:
                continue

            summary = self._clean_text(
                self._child_text(node, ["description", "summary", "content"])
            )
            source = self._clean_text(self._child_text(node, ["source"])) or self._source_from_title(title) or "RSS Feed"
            if source and title.endswith(f" - {source}"):
                title = title.rsplit(" - ", 1)[0].strip()
            url = self._child_link(node)
            published_at = self._parse_datetime(
                self._child_text(node, ["pubDate", "published", "updated", "dc:date"])
            )
            guid = self._clean_text(self._child_text(node, ["guid", "id"])) or url

            entries.append(
                {
                    "title": title,
                    "summary": summary,
                    "source": source,
                    "url": url,
                    "guid": guid,
                    "published_at": published_at,
                }
            )

        return entries

    def _child_text(self, node: ElementTree.Element, names: list[str]) -> str | None:
        normalized_names = {name.split(":")[-1] for name in names}
        for child in list(node):
            local_name = child.tag.split("}")[-1].split(":")[-1]
            if local_name in normalized_names:
                return "".join(child.itertext()).strip()
        return None

    def _child_link(self, node: ElementTree.Element) -> str:
        for child in list(node):
            local_name = child.tag.split("}")[-1]
            if local_name != "link":
                continue
            if child.text and child.text.strip():
                return child.text.strip()
            href = child.attrib.get("href")
            if href:
                return href.strip()
        return ""

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        cleaned = value.strip()
        try:
            parsed = parsedate_to_datetime(cleaned)
            return self._ensure_utc(parsed)
        except Exception:
            pass
        try:
            parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            return self._ensure_utc(parsed)
        except Exception:
            return None

    def _clean_text(self, value: str | None) -> str | None:
        if not value:
            return None
        text = html.unescape(re.sub(r"<[^>]+>", " ", value))
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    def _source_from_title(self, title: str) -> str | None:
        if " - " not in title:
            return None
        candidate = title.rsplit(" - ", 1)[-1].strip()
        if len(candidate) > 2 and len(candidate) < 80:
            return candidate
        return None

    def _build_dedupe_key(self, entry: dict) -> str:
        raw = "|".join(
            [
                entry.get("guid") or "",
                entry.get("url") or "",
                entry.get("title") or "",
                entry.get("source") or "",
                entry.get("published_at").isoformat() if entry.get("published_at") else "",
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _prepare_url(self, url: str, guid: str | None) -> str:
        if not url:
            return ""

        candidates = [url]
        if "?" in url:
            candidates.append(url.split("?", 1)[0])

        for candidate in candidates:
            if len(candidate) <= 500:
                return candidate

        if guid:
            fallback = f"https://news.google.com/rss/articles/{guid}"
            if len(fallback) <= 500:
                return fallback

        return url[:500]

    def _truncate(self, value: str | None, limit: int) -> str:
        if not value:
            return ""
        return value if len(value) <= limit else value[: limit - 1]

    def _match_symbols(self, title: str, summary: str | None, assets: list[Asset]) -> list[str]:
        haystack_upper = f"{title} {summary or ''}".upper()
        haystack_lower = haystack_upper.lower()
        matches: list[str] = []

        for asset in assets:
            symbol_candidates = {asset.symbol.upper()}
            if "." in asset.symbol:
                symbol_candidates.add(asset.symbol.split(".")[0].upper())

            symbol_match = any(
                len(candidate) >= 3 and re.search(rf"\b{re.escape(candidate)}\b", haystack_upper)
                for candidate in symbol_candidates
            )
            name_match = any(candidate in haystack_lower for candidate in self._name_candidates(asset.name))
            if symbol_match or name_match:
                matches.append(asset.symbol)
            if len(matches) >= 4:
                break

        return matches

    def _name_candidates(self, asset_name: str) -> list[str]:
        cleaned = re.sub(r"[^a-z0-9&+\s]", " ", asset_name.lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return []

        suffix_tokens = {"inc", "corp", "corporation", "co", "company", "ltd", "plc", "holdings", "trust", "etf", "fund", "ucits"}
        parts = [part for part in cleaned.split(" ") if part]
        candidates = {cleaned}
        while parts and parts[-1] in suffix_tokens:
            parts.pop()
        if parts:
            candidates.add(" ".join(parts))
            candidates.add(parts[0])
            if len(parts) >= 2:
                candidates.add(" ".join(parts[:2]))

        return [candidate for candidate in candidates if len(candidate) >= 4]

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=utcnow().tzinfo)
        return value.astimezone(utcnow().tzinfo)

    def _infer_sentiment(self, title: str, summary: str | None) -> str:
        text = f"{title} {summary or ''}".lower()
        positive_tokens = {"beat", "beats", "surge", "rally", "gain", "gains", "upgrade", "growth", "record", "rise"}
        negative_tokens = {"miss", "misses", "drop", "falls", "fall", "downgrade", "lawsuit", "probe", "cut", "warning"}

        positive_score = sum(1 for token in positive_tokens if token in text)
        negative_score = sum(1 for token in negative_tokens if token in text)
        if positive_score > negative_score:
            return "positive"
        if negative_score > positive_score:
            return "negative"
        return "neutral"

    def _infer_event_type(self, title: str, summary: str | None) -> str:
        article = NewsArticle(
            title=title,
            source="rss",
            url="https://placeholder.local",
            published_at=utcnow(),
            summary=summary,
            sentiment=None,
            impact_score=None,
            affected_symbols=[],
            provider_type="rss",
            model_name="rss-heuristic",
            dedupe_key=None,
            analysis_metadata={},
        )
        return event_extraction_service.infer_event_type(article)

    def _infer_impact_score(self, event_type: str, affected_symbols: list[str]) -> float:
        base_scores = {
            "earnings": 0.82,
            "guidance": 0.76,
            "analyst": 0.64,
            "regulation": 0.8,
            "macro": 0.7,
            "sector": 0.56,
        }
        base_score = base_scores.get(event_type, 0.55)
        if len(affected_symbols) >= 2:
            base_score += 0.05
        return min(base_score, 0.95)


news_service = NewsService()
