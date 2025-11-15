import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    limit: int = 20


class GeneratePitchRequest(BaseModel):
    query_id: str
    parameters: dict = {}


class ApproveDraftRequest(BaseModel):
    draft_id: str
    approved: bool


class SendEmailRequest(BaseModel):
    draft_id: str


@app.get("/")
def root():
    return {"message": "Newsletter Parser API running"}


@app.get("/schema")
def get_schema_info():
    """Expose schemas to the UI/database viewer"""
    from schemas import Settings, Query, Pitch, EmailDraft

    return {
        "collections": [
            {
                "name": "settings",
                "schema": Settings.model_json_schema(),
            },
            {
                "name": "query",
                "schema": Query.model_json_schema(),
            },
            {
                "name": "pitch",
                "schema": Pitch.model_json_schema(),
            },
            {
                "name": "emaildraft",
                "schema": EmailDraft.model_json_schema(),
            },
        ]
    }


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os

    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# In a real integration we would connect to Gmail via OAuth or app passwords using IMAP/SMTP.
# For this environment, we'll define placeholder endpoints that simulate the flow and persist data.


@app.post("/parse")
def parse_newsletters(req: ParseRequest):
    """
    Simulate parsing recent emails and extracting psych-relevant queries.
    Creates Query documents with optional deadlines.
    """
    now = datetime.now(timezone.utc)
    sample_items = []
    for i in range(req.limit):
        sample_items.append(
            {
                "subject": f"Call for psychology expert comment #{i+1}",
                "sender_email": f"editor{i+1}@newsletter.com",
                "sender_name": "Newsletter Editor",
                "received_at": now,
                "deadline": (now.replace(microsecond=0)),
                "body_text": "We're seeking a psychologist's perspective on workplace burnout and coping strategies.",
                "source_message_id": f"sim-{i+1}",
                "status": "new",
                "tags": ["psych", "newsletter"],
            }
        )

    inserted_ids = []
    for item in sample_items:
        try:
            _id = create_document("query", item)
            inserted_ids.append(_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return {"inserted": len(inserted_ids), "ids": inserted_ids}


@app.get("/queries")
def list_queries(status: Optional[str] = None):
    try:
        filter_dict = {"status": status} if status else {}
        docs = get_documents("query", filter_dict=filter_dict, limit=200)
        # Convert ObjectIds to strings
        for d in docs:
            if "_id" in d:
                d["_id"] = str(d["_id"])
            # Convert datetimes
            for k in ["received_at", "deadline", "created_at", "updated_at"]:
                if d.get(k) is not None:
                    d[k] = d[k].isoformat() if hasattr(d[k], "isoformat") else d[k]
        return {"items": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pitch")
def generate_pitch(req: GeneratePitchRequest):
    """
    Generate a pitch text for a query, using stored settings as a style sheet.
    """
    # Fetch settings (singleton)
    settings_docs = get_documents("settings", limit=1)
    style = settings_docs[0] if settings_docs else {
        "tone": "friendly",
        "voice": "First-person expert but approachable",
        "intro_template": "Hi {name},\n\nThanks for reaching out. I'm {your_name}, a {your_title}.",
        "signature_template": "\n\nBest,\n{your_name}\n{your_title}\n{your_website}",
        "your_name": "Your Name",
        "your_title": "Licensed Psychologist",
        "your_website": "yourwebsite.com",
    }

    # Find the query
    docs = get_documents("query", {"_id": {"$exists": True}}, limit=200)
    target = next((d for d in docs if str(d.get("_id")) == req.query_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Query not found")

    subject = target.get("subject", "")
    body = target.get("body_text", "")

    # Very simple pitch generation logic as placeholder
    pitch_lines = [
        f"Regarding: {subject}",
        "",
        "Key points I can contribute:",
        "- Evidence-based insights on burnout and coping",
        "- Practical takeaways grounded in CBT and behavioral science",
        "- Availability for quick follow-up if needed",
    ]

    if style.get("tone") == "formal":
        pitch_lines.append("I would be pleased to provide a concise, research-informed statement.")
    elif style.get("tone") == "confident":
        pitch_lines.append("I regularly comment for national outlets and can deliver a crisp quote.")
    else:
        pitch_lines.append("Happy to share a tight quote that serves your readers.")

    content = "\n".join(pitch_lines)

    doc = {
        "query_id": req.query_id,
        "content": content,
        "style_used": {
            "tone": style.get("tone"),
            "voice": style.get("voice"),
        },
        "created_at": datetime.now(timezone.utc),
    }

    try:
        pitch_id = create_document("pitch", doc)
        return {"pitch_id": pitch_id, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/draft")
def draft_email(req: GeneratePitchRequest):
    """
    Build an email draft combining intro + generated pitch + signature.
    """
    settings_docs = get_documents("settings", limit=1)
    style = settings_docs[0] if settings_docs else {
        "intro_template": "Hi {name},\n\nThanks for reaching out. I'm {your_name}, a {your_title}.",
        "signature_template": "\n\nBest,\n{your_name}\n{your_title}\n{your_website}",
        "your_name": "Your Name",
        "your_title": "Licensed Psychologist",
        "your_website": "yourwebsite.com",
    }

    # Find the query
    docs = get_documents("query", {"_id": {"$exists": True}}, limit=200)
    target = next((d for d in docs if str(d.get("_id")) == req.query_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Query not found")

    # If pitch exists, use it; otherwise generate basic
    pitch_docs = get_documents("pitch", {"query_id": req.query_id}, limit=1)
    pitch_content = pitch_docs[0].get("content") if pitch_docs else None
    if not pitch_content:
        pitch_content = "See below for my quick take: ..."

    name = target.get("sender_name") or "there"

    intro = style.get("intro_template", "").format(
        name=name,
        your_name=style.get("your_name", "Your Name"),
        your_title=style.get("your_title", "Licensed Psychologist"),
    )

    signature = style.get("signature_template", "").format(
        your_name=style.get("your_name", "Your Name"),
        your_title=style.get("your_title", "Licensed Psychologist"),
        your_website=style.get("your_website", "yourwebsite.com"),
    )

    body = f"{intro}\n\n{pitch_content}{signature}"

    draft_doc = {
        "query_id": req.query_id,
        "to_email": target.get("sender_email"),
        "subject": target.get("subject"),
        "body": body,
        "approved": False,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        draft_id = create_document("emaildraft", draft_doc)
        return {"draft_id": draft_id, "body": body}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/approve")
def approve_draft(req: ApproveDraftRequest):
    try:
        # naive update via pymongo since helper doesn't include update
        from bson import ObjectId
        result = db["emaildraft"].update_one(
            {"_id": ObjectId(req.draft_id)}, {"$set": {"approved": req.approved, "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Draft not found")
        return {"updated": bool(result.modified_count)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/send")
def send_email(req: SendEmailRequest):
    """
    Simulate sending the email. In production, integrate with Gmail SMTP using an app password.
    Only sends if draft is approved.
    """
    try:
        from bson import ObjectId
        draft = db["emaildraft"].find_one({"_id": ObjectId(req.draft_id)})
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        if not draft.get("approved"):
            raise HTTPException(status_code=400, detail="Draft not approved")

        # Simulate send: write a record to a 'sent' collection
        send_record = {
            "draft_id": str(draft.get("_id")),
            "to": draft.get("to_email"),
            "subject": draft.get("subject"),
            "body": draft.get("body"),
            "sent_at": datetime.now(timezone.utc),
        }
        _id = create_document("sent", send_record)

        # Update query status
        db["query"].update_one(
            {"_id": draft.get("query_id")}, {"$set": {"status": "sent", "updated_at": datetime.now(timezone.utc)}}
        )

        return {"sent_id": _id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
