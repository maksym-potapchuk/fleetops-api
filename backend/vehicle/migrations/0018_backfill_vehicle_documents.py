"""
Data migration: backfill VehicleDocument from existing TechnicalInspection.report.

Safe re-run: deduplicates by (vehicle_id, file path). Skips inspections without report.
Detects type by file extension: .pdf → pdf, everything else → photo.
Respects per-type limit of 2 per vehicle — oldest inspection reports copied first,
extras skipped so existing data cannot exceed the cap enforced by the API.

Irreversible on purpose: reverse is a no-op (rows will be removed by schema rollback).
"""

from django.db import migrations


PDF_EXTENSIONS = (".pdf",)
TYPE_PHOTO = "photo"
TYPE_PDF = "pdf"
MAX_PER_TYPE = 2


def _detect_type(path: str) -> str:
    return TYPE_PDF if path.lower().endswith(PDF_EXTENSIONS) else TYPE_PHOTO


def backfill_documents(apps, schema_editor):
    TechnicalInspection = apps.get_model("vehicle", "TechnicalInspection")
    VehicleDocument = apps.get_model("vehicle", "VehicleDocument")

    inspections = (
        TechnicalInspection.objects.exclude(report="")
        .exclude(report__isnull=True)
        .order_by("vehicle_id", "created_at", "id")
    )

    # Pre-load existing documents to avoid duplicates and respect caps.
    existing_by_vehicle: dict[int, dict[str, set[str]]] = {}
    for doc in VehicleDocument.objects.all().only(
        "vehicle_id", "document_type", "file"
    ):
        buckets = existing_by_vehicle.setdefault(
            doc.vehicle_id, {TYPE_PHOTO: set(), TYPE_PDF: set()}
        )
        buckets[doc.document_type].add(doc.file.name)

    to_create = []
    for insp in inspections.iterator():
        if not insp.report:
            continue
        path = insp.report.name
        if not path:
            continue

        buckets = existing_by_vehicle.setdefault(
            insp.vehicle_id, {TYPE_PHOTO: set(), TYPE_PDF: set()}
        )
        doc_type = _detect_type(path)

        if path in buckets[doc_type]:
            continue
        if len(buckets[doc_type]) >= MAX_PER_TYPE:
            continue

        to_create.append(
            VehicleDocument(
                vehicle_id=insp.vehicle_id,
                file=path,
                document_type=doc_type,
                created_by_id=insp.created_by_id,
                created_at=insp.created_at,
            )
        )
        buckets[doc_type].add(path)

    if not to_create:
        return
    created = VehicleDocument.objects.bulk_create(to_create, batch_size=500)
    # auto_now_add overrides bulk_create values — restore original created_at so
    # document history matches the inspection it was copied from.
    for doc, original in zip(created, to_create):
        if doc.created_at != original.created_at:
            VehicleDocument.objects.filter(pk=doc.pk).update(
                created_at=original.created_at
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("vehicle", "0017_vehicledocument"),
    ]

    operations = [
        migrations.RunPython(backfill_documents, noop_reverse),
    ]
