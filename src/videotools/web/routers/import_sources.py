from fastapi import APIRouter

from videotools.services.import_sources import discover_import_sources
from videotools.web.schemas import DetectedImportSourceResponse

router = APIRouter(prefix="/import-sources", tags=["imports"])


@router.get("", response_model=list[DetectedImportSourceResponse])
def get_import_sources() -> list[DetectedImportSourceResponse]:
    return [
        DetectedImportSourceResponse(
            path=source.path,
            label=source.label,
            source_type=source.source_type,
            reason=source.reason,
        )
        for source in discover_import_sources()
    ]
