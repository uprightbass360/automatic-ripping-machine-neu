"""API v1 — Drive endpoints."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from arm.database import db
from arm.models.system_drives import SystemDrives

router = APIRouter(prefix="/api/v1", tags=["drives"])


@router.patch('/drives/{drive_id}')
async def update_drive(drive_id: int, request: Request):
    """Update a drive's user-editable fields (name, description)."""
    drive = SystemDrives.query.get(drive_id)
    if not drive:
        return JSONResponse({"success": False, "error": "Drive not found"}, status_code=404)

    body = await request.json()
    if not body:
        return JSONResponse({"success": False, "error": "No fields to update"}, status_code=400)

    updated = {}
    if 'name' in body:
        drive.name = str(body['name']).strip()[:100]
        updated['name'] = drive.name
    if 'description' in body:
        drive.description = str(body['description']).strip()[:200]
        updated['description'] = drive.description
    if 'uhd_capable' in body:
        drive.uhd_capable = bool(body['uhd_capable'])
        updated['uhd_capable'] = drive.uhd_capable

    if not updated:
        return JSONResponse({"success": False, "error": "No valid fields provided"}, status_code=400)

    db.session.commit()
    return {"success": True, "drive_id": drive.drive_id}
