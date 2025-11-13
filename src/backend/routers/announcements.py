"""
Announcement endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from pydantic import BaseModel

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreate(BaseModel):
    message: str
    start_date: Optional[str] = None
    expiration_date: str
    is_active: bool = True


class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_announcements(active_only: bool = Query(True, description="Filter only active announcements")):
    """
    Get all announcements, optionally filtering by active status and date range
    
    - active_only: If True, only return active announcements within their date range
    """
    today = date.today().isoformat()
    
    # Build query
    query = {}
    if active_only:
        query["is_active"] = True
        query["expiration_date"] = {"$gte": today}
    
    # Fetch announcements
    announcements = []
    for announcement in announcements_collection.find(query):
        # Check if announcement should be shown based on start_date
        if active_only and announcement.get("start_date"):
            if announcement["start_date"] > today:
                continue
        
        announcement["id"] = str(announcement["_id"])
        del announcement["_id"]
        announcements.append(announcement)
    
    return announcements


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(announcement: AnnouncementCreate, teacher_username: str = Query(...)):
    """Create a new announcement - requires teacher authentication"""
    # Verify teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    
    # Validate dates
    try:
        exp_date = datetime.strptime(announcement.expiration_date, "%Y-%m-%d").date()
        today = date.today()
        
        if exp_date < today:
            raise HTTPException(status_code=400, detail="Expiration date cannot be in the past")
        
        if announcement.start_date:
            start_date = datetime.strptime(announcement.start_date, "%Y-%m-%d").date()
            if start_date > exp_date:
                raise HTTPException(status_code=400, detail="Start date cannot be after expiration date")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Create announcement document
    announcement_doc = announcement.dict()
    
    # Insert into database
    result = announcements_collection.insert_one(announcement_doc)
    
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create announcement")
    
    announcement_doc["id"] = str(result.inserted_id)
    if "_id" in announcement_doc:
        del announcement_doc["_id"]
    
    return announcement_doc


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str, 
    announcement: AnnouncementUpdate, 
    teacher_username: str = Query(...)
):
    """Update an existing announcement - requires teacher authentication"""
    from bson.objectid import ObjectId
    
    # Verify teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    
    # Validate announcement exists
    try:
        obj_id = ObjectId(announcement_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    existing = announcements_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Build update document
    update_doc = {}
    if announcement.message is not None:
        update_doc["message"] = announcement.message
    if announcement.start_date is not None:
        update_doc["start_date"] = announcement.start_date
    if announcement.expiration_date is not None:
        update_doc["expiration_date"] = announcement.expiration_date
    if announcement.is_active is not None:
        update_doc["is_active"] = announcement.is_active
    
    # Validate dates if provided
    if update_doc:
        exp_date = update_doc.get("expiration_date", existing.get("expiration_date"))
        start_date = update_doc.get("start_date", existing.get("start_date"))
        
        try:
            exp_date_obj = datetime.strptime(exp_date, "%Y-%m-%d").date()
            
            if start_date:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                if start_date_obj > exp_date_obj:
                    raise HTTPException(status_code=400, detail="Start date cannot be after expiration date")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Update announcement
    result = announcements_collection.update_one(
        {"_id": obj_id},
        {"$set": update_doc}
    )
    
    if result.modified_count == 0 and result.matched_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update announcement")
    
    # Return updated announcement
    updated = announcements_collection.find_one({"_id": obj_id})
    updated["id"] = str(updated["_id"])
    del updated["_id"]
    
    return updated


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: str = Query(...)):
    """Delete an announcement - requires teacher authentication"""
    from bson.objectid import ObjectId
    
    # Verify teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    
    # Validate announcement exists
    try:
        obj_id = ObjectId(announcement_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    result = announcements_collection.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}
