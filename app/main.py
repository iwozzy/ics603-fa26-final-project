"""FastAPI routes and a basic movie discovery page."""

from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.agent import Movie, Person, SearchRequest, SearchResponse

app = FastAPI(title="Lumière")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return Path(__file__).with_name("page.html").read_text(encoding="utf-8")


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Return the same sample data for every valid request."""
    return SearchResponse(
        message="Placeholder results only. No search or extraction was performed.",
        people=[
            Person(
                name="Matthew McConaughey",
                role="Actor",
                known_for=["Interstellar", "Dallas Buyers Club", "Sing"],
            )
        ],
        movies=[
            Movie(
                title="Interstellar",
                release_year=2014,
                release_date=date(2014, 11, 7),
                tagline="Sample movie result",
                storyline="A space exploration story, shown as fixed sample data.",
                genres=["Science Fiction", "Drama"],
                runtime_minutes=169,
                cast=[Person(name="Matthew McConaughey", role="Cooper")],
                crew=[Person(name="Christopher Nolan", role="Director")],
            )
        ],
    )
