from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class TicketBase(BaseModel):
    title: str = Field(description="Clear, concise Jira-style ticket title")
    problem_statement: str = Field(description="Precise description of the technical debt, bug, or missing feature")
    motivation: str = Field(description="Engineering rationale and expected benefits")
    current_behavior: str = Field(description="How the system currently behaves or where it falls short")
    desired_behavior: str = Field(description="Expected behavior after the ticket is resolved")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Explicit testable conditions that must pass")
    proposed_tests: List[str] = Field(default_factory=list, description="Deterministic test functions or assertions to add")
    relevant_graph_entities: List[str] = Field(default_factory=list, description="Symbols, classes, or modules identified from graph/AST")
    candidate_files: List[str] = Field(default_factory=list, description="Target source files within allowed repository scope")
    risk_level: str = Field(default="low", description="Risk level: low, medium, high")
    expected_complexity: str = Field(default="small", description="Complexity: small, medium, large")
    estimated_resources: str = Field(default="1 LLM call, 1 pytest run", description="Estimated compute and test budget")
    evidence: List[str] = Field(default_factory=list, description="Concrete evidence found in AST or logs")
    out_of_scope: Optional[str] = Field(default=None, description="Explicitly protected or excluded files and behaviors")

class TicketCreate(TicketBase):
    repo_id: str

class TicketUpdate(BaseModel):
    title: Optional[str] = None
    problem_statement: Optional[str] = None
    motivation: Optional[str] = None
    current_behavior: Optional[str] = None
    desired_behavior: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    proposed_tests: Optional[List[str]] = None
    candidate_files: Optional[List[str]] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None

class TicketResponse(TicketBase):
    id: str
    repo_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TicketGenerationRequest(BaseModel):
    repo_id: str = "agent_chess"
    target_area: Optional[str] = None
    custom_prompt: Optional[str] = None
