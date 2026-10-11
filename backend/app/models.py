from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey,
                        Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)


class PO(Base):
    __tablename__ = "pos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(50), unique=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    total: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="open")
    issued: Mapped[date] = mapped_column(Date)
    lines: Mapped[list["POLine"]] = relationship(back_populates="po", cascade="all,delete")
    matches: Mapped[list["Match"]] = relationship(back_populates="po")
    vendor = relationship("Vendor")

    @property
    def invoiced_total(self) -> float:
        return round(sum(m.invoice_total or 0 for m in self.matches
                         if m.run.decision == "AUTO-APPROVE"), 2)


class POLine(Base):
    __tablename__ = "po_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("pos.id"))
    description: Mapped[str] = mapped_column(Text)
    qty: Mapped[float] = mapped_column(Float)
    unit_price: Mapped[float] = mapped_column(Float)
    po = relationship("PO", back_populates="lines")


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    mime: Mapped[str] = mapped_column(String(100), default="application/pdf")
    size: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str] = mapped_column(String(20), default="PENDING")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(Text, default="")
    po_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    extraction: Mapped["Extraction | None"] = relationship(back_populates="run",
                                                           cascade="all,delete", uselist=False)
    match: Mapped["Match | None"] = relationship(back_populates="run",
                                                  cascade="all,delete", uselist=False)
    events: Mapped[list["StageEvent"]] = relationship(back_populates="run",
                                                       cascade="all,delete")


class Extraction(Base):
    __tablename__ = "extractions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    source: Mapped[str] = mapped_column(String(20))          # text | ocr | fallback
    fields: Mapped[dict] = mapped_column(JSON, default=dict)  # ExtractedInvoice dict
    field_confidence: Mapped[dict] = mapped_column(JSON, default=dict)
    run = relationship("Run", back_populates="extraction")


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    po_id: Mapped[int | None] = mapped_column(ForeignKey("pos.id"), nullable=True)
    method: Mapped[str] = mapped_column(String(20))           # ref | heuristic | none
    invoice_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    po_remaining: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_abs: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)  # full MatchResult dict
    run = relationship("Run", back_populates="match")
    po = relationship("PO", back_populates="matches")


class StageEvent(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    stage: Mapped[str] = mapped_column(String(30))            # receive..report
    status: Mapped[str] = mapped_column(String(20))           # start | ok | warn | error
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    run = relationship("Run", back_populates="events")


class InvoiceSeen(Base):
    """Duplicate register: (vendor, invoice number) pairs from prior runs."""
    __tablename__ = "invoices_seen"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_name: Mapped[str] = mapped_column(String(200))
    invoice_number: Mapped[str] = mapped_column(String(100))
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
