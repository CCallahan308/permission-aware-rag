import uuid
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.embeddings import embed_texts

METROPOLITAN_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
ST_JUDE_TENANT_ID = UUID("00000000-0000-0000-0000-000000000002")

USERS_METROPOLITAN = [
    {
        "id": UUID("10000000-0000-0000-0000-000000000001"),
        "tenant_id": METROPOLITAN_TENANT_ID,
        "email": "physician@metropolitan.org",
        "role": "physician",
        "clearance_level": 3
    },
    {
        "id": UUID("10000000-0000-0000-0000-000000000002"),
        "tenant_id": METROPOLITAN_TENANT_ID,
        "email": "nurse@metropolitan.org",
        "role": "nurse",
        "clearance_level": 2
    },
    {
        "id": UUID("10000000-0000-0000-0000-000000000003"),
        "tenant_id": METROPOLITAN_TENANT_ID,
        "email": "billing@metropolitan.org",
        "role": "billing_specialist",
        "clearance_level": 1
    },
    {
        "id": UUID("10000000-0000-0000-0000-000000000004"),
        "tenant_id": METROPOLITAN_TENANT_ID,
        "email": "auditor@metropolitan.org",
        "role": "auditor",
        "clearance_level": 4
    }
]

USERS_ST_JUDE = [
    {
        "id": UUID("20000000-0000-0000-0000-000000000001"),
        "tenant_id": ST_JUDE_TENANT_ID,
        "email": "physician@stjude.org",
        "role": "physician",
        "clearance_level": 3
    }
]

def seed_tenants_and_users(db: Session) -> None:
    # Seed Hospital Tenants
    db.execute(
        text("""
            INSERT INTO hospital_tenants (id, name, subdomain)
            VALUES 
                (:m_id, 'Metropolitan General Hospital', 'metropolitan'),
                (:s_id, 'St. Jude Regional Medical', 'stjude')
            ON CONFLICT (id) DO NOTHING;
        """),
        {"m_id": str(METROPOLITAN_TENANT_ID), "s_id": str(ST_JUDE_TENANT_ID)}
    )
    
    # Seed Users
    all_users = USERS_METROPOLITAN + USERS_ST_JUDE
    for u in all_users:
        db.execute(
            text("""
                INSERT INTO hospital_users (id, tenant_id, email, role, clearance_level)
                VALUES (:id, :tenant_id, :email, :role, :clearance_level)
                ON CONFLICT (id) DO UPDATE SET
                    role = EXCLUDED.role,
                    clearance_level = EXCLUDED.clearance_level;
            """),
            {
                "id": str(u["id"]),
                "tenant_id": str(u["tenant_id"]),
                "email": u["email"],
                "role": u["role"],
                "clearance_level": u["clearance_level"]
            }
        )
    db.commit()

def ingest_document_with_chunks(
    db: Session,
    tenant_id: UUID,
    title: str,
    document_type: str,
    classification_level: int,
    allowed_roles: List[str],
    chunk_contents: List[str],
    embeddings: Optional[List[List[float]]] = None,
    document_id: Optional[UUID] = None
) -> UUID:
    doc_id = document_id or uuid.uuid4()
    
    db.execute(
        text("""
            INSERT INTO documents (
                id, tenant_id, title, document_type, classification_level, allowed_roles
            ) VALUES (
                :id, :tenant_id, :title, :document_type, :classification_level, :allowed_roles
            );
        """),
        {
            "id": str(doc_id),
            "tenant_id": str(tenant_id),
            "title": title,
            "document_type": document_type,
            "classification_level": classification_level,
            "allowed_roles": allowed_roles
        }
    )
    
    if embeddings is None:
        embeddings = embed_texts(chunk_contents)
    
    for idx, (content, emb) in enumerate(zip(chunk_contents, embeddings)):
        chunk_id = uuid.uuid4()
        emb_str = f"[{','.join(str(float(x)) for x in emb)}]"
        db.execute(
            text("""
                INSERT INTO document_chunks (
                    id, document_id, tenant_id, chunk_index, content, embedding, allowed_roles, classification_level
                ) VALUES (
                    :id, :document_id, :tenant_id, :chunk_index, :content, CAST(:embedding AS vector), :allowed_roles, :classification_level
                );
            """),
            {
                "id": str(chunk_id),
                "document_id": str(doc_id),
                "tenant_id": str(tenant_id),
                "chunk_index": idx,
                "content": content,
                "embedding": emb_str,
                "allowed_roles": allowed_roles,
                "classification_level": classification_level
            }
        )
    db.commit()
    return doc_id

def seed_synthetic_hospital_corpus(db: Session) -> Dict[str, int]:
    seed_tenants_and_users(db)
    
    total_docs = 0
    total_chunks = 0
    
    # 1. Metropolitan General Hospital - Clinical Guidelines (Class 1, all roles)
    mgh_guideline_chunks = [
        "Metropolitan General Hospital Clinical Protocol: Emergency Department Sepsis Resuscitation Pathway. Initiate lactate measurement within 60 minutes.",
        "Metropolitan Sepsis Protocol: Administer 30 mL/kg crystalloid fluid bolus for hypotension or lactate >= 4.0 mmol/L within the first 3 hours.",
        "Metropolitan Stroke Management Protocol: Perform non-contrast head CT within 20 minutes of arrival for suspected acute ischemic stroke."
    ]
    ingest_document_with_chunks(
        db=db,
        tenant_id=METROPOLITAN_TENANT_ID,
        title="MGH Emergency Clinical Guidelines SOP",
        document_type="clinical_guideline",
        classification_level=1,
        allowed_roles=["physician", "nurse", "billing_specialist", "auditor"],
        chunk_contents=mgh_guideline_chunks
    )
    total_docs += 1
    total_chunks += len(mgh_guideline_chunks)
    
    # 2. Metropolitan General Hospital - Chargemaster & Billing Schedules (Class 1, billing_specialist)
    mgh_billing_chunks = [
        "Metropolitan General Hospital Chargemaster Schedule: CPT 99285 Emergency department visit comprehensive complexity. Standard allowable fee: $1,250.00.",
        "Metropolitan Billing Guideline: ICD-10-CM Code R65.20 Severe sepsis without septic shock. Requires clinical documentation of organ dysfunction.",
        "Metropolitan Billing Schedule: CPT 99291 Critical care evaluation first 30-74 minutes. Reimbursement rate negotiated with commercial payors at 180% Medicare."
    ]
    ingest_document_with_chunks(
        db=db,
        tenant_id=METROPOLITAN_TENANT_ID,
        title="MGH Chargemaster and CPT Coding Fee Schedule 2026",
        document_type="billing_schedule",
        classification_level=1,
        allowed_roles=["billing_specialist"],
        chunk_contents=mgh_billing_chunks
    )
    total_docs += 1
    total_chunks += len(mgh_billing_chunks)
    
    # 3. Metropolitan General Hospital - Nursing Daily Care Notes (Class 2, nurse & physician)
    mgh_nurse_chunks = [
        "Metropolitan EHR Nursing Note - Patient MGH-1049: Vital signs stable. Blood pressure 122/78 mmHg, heart rate 74 bpm, SpO2 98% on room air.",
        "Metropolitan EHR Nursing Note - Patient MGH-2088: Post-operative wound site clean and intact. Dressing changed per sterile protocol. Patient reports pain score 2/10."
    ]
    ingest_document_with_chunks(
        db=db,
        tenant_id=METROPOLITAN_TENANT_ID,
        title="MGH Inpatient Nursing Care Encounter Notes",
        document_type="ehr_clinical_note",
        classification_level=2,
        allowed_roles=["physician", "nurse"],
        chunk_contents=mgh_nurse_chunks
    )
    total_docs += 1
    total_chunks += len(mgh_nurse_chunks)
    
    # 4. Metropolitan General Hospital - Physician Progress & Psychiatric Evaluation (Class 3, physician only)
    mgh_physician_chunks = [
        "Metropolitan EHR Physician Progress Note - Patient MGH-3312: Differential diagnosis includes acute decompensated heart failure with preserved ejection fraction.",
        "Metropolitan EHR Psychiatric Evaluation - Patient MGH-5099: Comprehensive psychiatric evaluation reveals major depressive episode with severe anxious distress. Commenced escitalopram."
    ]
    ingest_document_with_chunks(
        db=db,
        tenant_id=METROPOLITAN_TENANT_ID,
        title="MGH Physician Clinical & Psychiatric Progress Notes",
        document_type="ehr_clinical_note",
        classification_level=3,
        allowed_roles=["physician"],
        chunk_contents=mgh_physician_chunks
    )
    total_docs += 1
    total_chunks += len(mgh_physician_chunks)

    # 5. Metropolitan General Hospital - Executive Mortality & Morbidity Review (Class 4, auditor only)
    mgh_audit_chunks = [
        "Metropolitan Executive Mortality Review Report #MGH-REV-2026-04: Confidential peer review of surgical adverse event. Root-cause analysis completed.",
        "Metropolitan Compliance Audit #AUD-882: Hospital quality assurance review of sentinel events and patient safety incident disclosures."
    ]
    ingest_document_with_chunks(
        db=db,
        tenant_id=METROPOLITAN_TENANT_ID,
        title="MGH Executive Mortality Review and Incident Reports",
        document_type="compliance_audit",
        classification_level=4,
        allowed_roles=["auditor"],
        chunk_contents=mgh_audit_chunks
    )
    total_docs += 1
    total_chunks += len(mgh_audit_chunks)

    # 6. St. Jude Regional Medical - Confidential Patient EHR Records (Tenant 2 isolation target)
    stjude_ehr_chunks = [
        "St. Jude Regional Medical EHR Record - Patient STJ-9821: Arthur Pendelton, confidential oncology progress note. Stage III colon adenocarcinoma undergoing FOLFOX chemotherapy.",
        "St. Jude Regional Medical Clinical Encounter - Patient STJ-4410: Diagnostic workup confirms severe pulmonary arterial hypertension. Prescribed sildenafil and bosentan.",
        "St. Jude Regional Medical Discharge Summary - Patient STJ-1102: Post-coronary artery bypass graft surgical summary and cardiac rehabilitation plan."
    ]
    ingest_document_with_chunks(
        db=db,
        tenant_id=ST_JUDE_TENANT_ID,
        title="St. Jude Regional Confidential Oncology & EHR Records",
        document_type="ehr_clinical_note",
        classification_level=3,
        allowed_roles=["physician"],
        chunk_contents=stjude_ehr_chunks
    )
    total_docs += 1
    total_chunks += len(stjude_ehr_chunks)

    # 7. St. Jude Regional Medical - Billing and Chargemaster (Tenant 2)
    stjude_billing_chunks = [
        "St. Jude Regional Medical Chargemaster: CPT 71046 Chest radiograph 2 views. Hospital charge: $420.00.",
        "St. Jude Regional Billing Policy: Inpatient diagnostic related group DRG 470 major joint replacement allowable schedule."
    ]
    ingest_document_with_chunks(
        db=db,
        tenant_id=ST_JUDE_TENANT_ID,
        title="St. Jude Regional Billing Fee Schedules",
        document_type="billing_schedule",
        classification_level=1,
        allowed_roles=["billing_specialist"],
        chunk_contents=stjude_billing_chunks
    )
    total_docs += 1
    total_chunks += len(stjude_billing_chunks)

    return {
        "documents_ingested": total_docs,
        "chunks_ingested": total_chunks
    }
