"""FastAPI routes and a basic movie discovery page."""

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator
from pydantic_ai.exceptions import AgentRunError, ModelRequestTimeout, ModelTimeoutError

from app.agent import (
    ExtractedTitles,
    Movie,
    NoteExtractionConfigurationError,
    Person,
    SearchRequest,
    SearchResponse,
    create_note_agent,
    extract_note_titles,
)
from app.rules.extraction import normalize_titles, validate_note

app = FastAPI(title="Lumière")


class NoteExtractionRequest(BaseModel):
    note: str

    @field_validator("note")
    @classmethod
    def validate_note_field(cls, note: str) -> str:
        return validate_note(note)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return Path(__file__).with_name("page.html").read_text(encoding="utf-8")


@app.post("/extract-note", response_model=ExtractedTitles)
async def extract_note(request: NoteExtractionRequest) -> ExtractedTitles:
    try:
        extracted = await extract_note_titles(request.note, create_note_agent())
    except NoteExtractionConfigurationError as exc:
        raise HTTPException(503, "Note extraction is not configured.") from exc
    except (ModelRequestTimeout, ModelTimeoutError, TimeoutError) as exc:
        raise HTTPException(
            504, "Movie title extraction timed out. Try again."
        ) from exc
    except AgentRunError as exc:
        raise HTTPException(502, "Could not extract movie titles. Try again.") from exc
    return ExtractedTitles(titles=normalize_titles(extracted.titles))


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
