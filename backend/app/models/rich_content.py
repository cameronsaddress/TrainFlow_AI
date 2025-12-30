from typing import Literal, List, Optional, Union, Annotated
from pydantic import BaseModel, Field

# --- Base Block ---
class ContentBlock(BaseModel):
    type: str

# --- Text Block ---
class TextBlock(ContentBlock):
    type: Literal["text"] = "text"
    content: str = Field(description="Markdown formatted text content.")

# --- Table Block ---
class TableRow(BaseModel):
    values: List[str] = Field(description="List of cell values for this row.")

class TableBlock(ContentBlock):
    type: Literal["table"] = "table"
    title: str = Field(description="Title or caption for the table.")
    headers: List[str] = Field(description="Column headers.")
    rows: List[List[str]] = Field(description="Data rows (list of strings).")
    notes: Optional[str] = Field(description="Footnotes or context for the table.", default=None)

# --- Alert Block ---
class AlertBlock(ContentBlock):
    type: Literal["alert"] = "alert"
    alert_type: Literal["safety", "compliance", "critical_info", "tip", "warning"] = Field(description="Type of alert determines visual styling.")
    title: str = Field(description="Header for the alert.")
    content: str = Field(description="The body of the alert/warning.")

# --- Quiz Block ---
class QuizOption(BaseModel):
    text: str = Field(description="The answer option text.")
    is_correct: bool = Field(description="True if this is the correct answer.", default=False)
    explanation: str = Field(description="Explanation of why this option is correct or incorrect.", default="")

class QuizBlock(ContentBlock):
    type: Literal["quiz"] = "quiz"
    question: str = Field(description="The question text.")
    options: List[QuizOption] = Field(description="List of multiple choice options (3-4 options).")

# --- Definition Block ---
class DefinitionBlock(ContentBlock):
    type: Literal["definition"] = "definition"
    term: str = Field(description="The technical term being defined.")
    definition: str = Field(description="The clear, concise definition.")

# --- PDF Reference ---
class PdfReference(BaseModel):
    document_id: int = Field(description="ID of the source document.")
    page_number: int = Field(description="Page number to display.")
    label: str = Field(description="Display label, e.g. 'Standard 1.3'")
    anchor_text: Optional[str] = Field(description="Text to search for dynamically at runtime to correct page offset.", default=None)

# --- Video Reference ---
class VideoReference(BaseModel):
    video_filename: str = Field(description="The filename of the matched video")
    start_time: float = Field(description="Start time in seconds")
    end_time: float = Field(description="End time in seconds")
    reason: str = Field(description="Why this clip is a perfect match")

# --- Container Model ---
class HybridLessonRichContent(BaseModel):
    learning_objective: str = Field(description="A clear, concise target outcome for the student.")
    estimated_reading_time_minutes: int = Field(description="Estimated reading time in minutes.", default=5)
    
    # Polymorphic list of blocks with Discriminator
    content_blocks: List[Annotated[Union[TextBlock, TableBlock, AlertBlock, QuizBlock, DefinitionBlock], Field(discriminator="type")]] = Field(
        description="The ordered sequence of content blocks that make up the lesson."
    )
    
    voiceover_summary: str = Field(description="A spoken-word style summary of the lesson, suitable for audio generation.")
    key_takeaways: List[str] = Field(description="3-5 key bullet points summarizing the lesson.", default_factory=list)
    
    pdf_reference: Optional[PdfReference] = Field(description="Link to the specific PDF page source.", default=None)
    source_clips: List[VideoReference] = Field(description="Video clips that demonstrate concepts in this lesson.", default_factory=list)

class VideoMatch(BaseModel):
    lesson_id: str = Field(description="The unique ID or Title of the lesson this clip belongs to.")
    video_filename: str
    start_time: float
    end_time: float
    reason: str

class GlobalVideoMatchResponse(BaseModel):
    matches: List[VideoMatch]
