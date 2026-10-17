"""Pydantic schemas: the contract every LLM output must satisfy."""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total: float


class Invoice(BaseModel):
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    line_items: List[LineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    payment_terms: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v):
        return v.strip().upper() if v else v


class InvoiceExtraction(Invoice):
    """What we ask the LLM for: the invoice fields plus its own confidence."""
    confidence: int = Field(
        ge=1, le=5,
        description="1-5: how confident you are the extraction is complete and correct",
    )
