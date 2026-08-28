"""
Hasta Kimlik Yönetimi API Router
=================================
TC hash tabanlı hasta arama, kayıt ve ziyaret geçmişi endpoint'leri.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from audit.logger import (
    AuditLogger,
    Patient,
    hash_tc,
    encrypt_field,
    decrypt_field,
)
from api.routes.auth import require_any_role

router = APIRouter(prefix="/patients", tags=["patients"])

# ─── Dependency ───────────────────────────────────────────────────────────────

def get_audit_logger() -> AuditLogger:
    from api.main import audit_logger
    return audit_logger


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class PatientCreate(BaseModel):
    tc_no: str = Field(..., min_length=11, max_length=11, pattern=r"^\d{11}$")
    ad_soyad: str = Field(..., min_length=2, max_length=150)
    dogum_tarihi: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    cinsiyet: Optional[str] = Field(default=None)
    telefon: Optional[str] = Field(default=None)
    kan_grubu: Optional[str] = Field(default=None)
    ilk_tani_tarihi: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    hekim_notu: Optional[str] = Field(default=None)


class PatientResponse(BaseModel):
    tc_hash: str
    tc_masked: str
    ad_soyad: str
    dogum_tarihi: Optional[str]
    cinsiyet: Optional[str]
    telefon: Optional[str]
    kan_grubu: Optional[str]
    ilk_tani_tarihi: Optional[str]
    hekim_notu: Optional[str]
    kayit_tarihi: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mask_tc(tc: str) -> str:
    return "*" * 7 + tc[-4:]


def _patient_to_response(p: Patient) -> PatientResponse:
    tc_plain = decrypt_field(p.tc_encrypted)
    ad_soyad_plain = decrypt_field(p.ad_soyad)
    dogum_plain = decrypt_field(p.dogum_tarihi) if p.dogum_tarihi else None
    telefon_plain = decrypt_field(p.telefon) if p.telefon else None
    hekim_notu_plain = decrypt_field(p.hekim_notu) if p.hekim_notu else None

    return PatientResponse(
        tc_hash=p.tc_hash,
        tc_masked=_mask_tc(tc_plain),
        ad_soyad=ad_soyad_plain,
        dogum_tarihi=dogum_plain,
        cinsiyet=p.cinsiyet,
        telefon=telefon_plain,
        kan_grubu=p.kan_grubu,
        ilk_tani_tarihi=str(p.ilk_tani_tarihi) if p.ilk_tani_tarihi else None,
        hekim_notu=hekim_notu_plain,
        kayit_tarihi=p.kayit_tarihi.isoformat(),
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/search", response_model=PatientResponse)
async def search_patient(
    tc: str = Query(..., min_length=1),
    logger: AuditLogger = Depends(get_audit_logger),
    _: dict = Depends(require_any_role),
):
    """TC numarasına göre hasta ara. Bulunmazsa 404 döner."""
    if not tc.isdigit():
        raise HTTPException(status_code=400, detail="TC Kimlik No yalnızca rakamlardan oluşmalıdır.")

    tc_hash = hash_tc(tc)
    with logger.SessionLocal() as session:
        patient = session.query(Patient).filter(Patient.tc_hash == tc_hash).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Hasta bulunamadı.")

    return _patient_to_response(patient)


@router.post("/", response_model=PatientResponse, status_code=201)
async def create_patient(
    data: PatientCreate,
    logger: AuditLogger = Depends(get_audit_logger),
    _: dict = Depends(require_any_role),
):
    """Yeni hasta kaydı oluştur. TC zaten kayıtlıysa 409 döner."""
    tc_hash = hash_tc(data.tc_no)

    with logger.SessionLocal() as session:
        existing = session.query(Patient).filter(Patient.tc_hash == tc_hash).first()
        if existing:
            raise HTTPException(status_code=409, detail="Bu TC numarasına ait hasta zaten kayıtlı.")

        ilk_tani = None
        if data.ilk_tani_tarihi:
            try:
                ilk_tani = date.fromisoformat(data.ilk_tani_tarihi)
            except ValueError:
                raise HTTPException(status_code=400, detail="ilk_tani_tarihi YYYY-MM-DD formatında olmalıdır.")

        patient = Patient(
            tc_hash=tc_hash,
            tc_encrypted=encrypt_field(data.tc_no),
            ad_soyad=encrypt_field(data.ad_soyad),
            dogum_tarihi=encrypt_field(data.dogum_tarihi) if data.dogum_tarihi else None,
            cinsiyet=data.cinsiyet,
            telefon=encrypt_field(data.telefon) if data.telefon else None,
            kan_grubu=data.kan_grubu,
            ilk_tani_tarihi=ilk_tani,
            hekim_notu=encrypt_field(data.hekim_notu) if data.hekim_notu else None,
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        return _patient_to_response(patient)


@router.get("/{tc_hash}/visits")
async def get_patient_visits(
    tc_hash: str,
    logger: AuditLogger = Depends(get_audit_logger),
    _: dict = Depends(require_any_role),
):
    """Bir hastanın tüm değerlendirme geçmişini döner (en yeniden eskiye)."""
    logs = logger.get_logs_by_tc_hash(tc_hash=tc_hash, limit=50)
    return {"tc_hash": tc_hash, "visits": logs}
