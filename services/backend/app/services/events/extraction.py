from app.models.news import NewsArticle


class EventExtractionService:
    def infer_event_type(self, article: NewsArticle) -> str:
        text = f"{article.title} {article.summary or ''}".lower()
        if "earnings" in text or "quarter" in text:
            return "earnings"
        if "guidance" in text:
            return "guidance"
        if "analyst" in text:
            return "analyst"
        if "regulation" in text or "lawsuit" in text:
            return "regulation"
        if "fed" in text or "macro" in text:
            return "macro"
        return "sector"


event_extraction_service = EventExtractionService()
