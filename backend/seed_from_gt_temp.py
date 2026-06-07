import os
import json
import uuid
import re
from pathlib import Path

# Add app package to sys.path
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.announcement import Announcement, Attachment
from app.models.eligibility import EligibilityResult, ExclusionResult
from app.models.match_result import MatchResult
from app.models.company import Company
from app.worker.tasks import match_company_announcements

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GT_DIR = PROJECT_ROOT / "evaluation" / "ground_truth"

def fix_attachments():
    db = SessionLocal()
    try:
        print("Re-seeding attachments and fixing missing paths from Ground Truth...")
        gt_folders = sorted([d for d in GT_DIR.iterdir() if d.is_dir() and d.name.startswith("ann_")])
        
        for folder in gt_folders:
            ann_id = folder.name
            
            # Find the Announcement
            ann = db.query(Announcement).filter(Announcement.source_id == ann_id).first()
            if not ann:
                print(f"Announcement {ann_id} does not exist. Skipping.")
                continue
            
            # Delete existing attachments for this announcement
            db.query(Attachment).filter(Attachment.announcement_id == ann.id).delete()
            
            # Find PDF files in the ground truth folder
            pdf_files = list(folder.glob("*.pdf"))
            for pdf_file in pdf_files:
                # Convert host path to container path
                # Host: c:\Users\Bang\doc-jipge\doc-jipge\evaluation\ground_truth\ann_XXX\*.pdf
                # Container: /evaluation/ground_truth/ann_XXX/*.pdf
                rel_path = pdf_file.relative_to(PROJECT_ROOT)
                container_path = "/" + str(rel_path).replace("\\", "/")
                
                att = Attachment(
                    id=uuid.uuid4(),
                    announcement_id=ann.id,
                    file_name=pdf_file.name,
                    file_type="pdf",
                    local_path=container_path,
                    conversion_status="converted"
                )
                db.add(att)
                print(f"Re-linked attachment for {ann_id}: {pdf_file.name} -> {container_path}")
                
        db.commit()
        
        # Double check missing files count
        atts = db.query(Attachment).all()
        missing = 0
        for a in atts:
            if a.local_path:
                # Resolve inside the container environment
                p = Path(a.local_path)
                if not p.exists():
                    missing += 1
            else:
                missing += 1
                
        print(f"Re-seeding completed. Total attachments: {len(atts)}, Missing files: {missing}")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding attachments: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_attachments()
