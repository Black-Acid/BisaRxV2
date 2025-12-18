from fastapi import FastAPI, Depends, HTTPException, security, APIRouter, Request, Query
from sqlalchemy import orm
from app import services as sv
import app.schemas as sma
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.handlers import _rate_limit_exceeded_handler
from app import models
from uuid import UUID

limiter =Limiter(key_func=get_remote_address)
router = APIRouter()
app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/")
async def status():
    return {"Status": "We are working perfectly"}

@app.post("/api/register/")
async def register_user(user: sma.LoginRequest, db: orm.Session = Depends(sv.get_db)):
    checked_user = await sv.get_user(user, db)
    if checked_user:
        raise HTTPException(status_code=400, detail="A user with this email already exists")
    try:
        creating_user = await sv.create_user(user, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad request: {e}")
    
    return await  sv.create_token(creating_user)


@app.post("/api/login")
async def login(
    form_data: sma.LoginRequest,
    db: orm.Session = Depends(sv.get_db)
):
    db_user = await sv.login(form_data.email, form_data.password, db)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return await sv.create_token(db_user)

@app.post("/chat", response_model=sma.ChatResponse)
@limiter.limit("5/minute")  # Rate limit
async def chat(
    request: Request, 
    payload: sma.ChatRequest, 
    db: orm.Session = Depends(sv.get_db), 
    current_user: models.UserModel = Depends(sv.get_current_user)
):
    """
    Route handler for chat. Delegates all logic to services.py
    """
    result = await sv.handle_chat4(payload, db, current_user)
    return result


@app.get("/sessions/", response_model=sma.ChatSessionsResponse)
async def get_chat_sessions(
    db: orm.Session = Depends(sv.get_db), 
    user: models.UserModel = Depends(sv.get_current_user)
):
    return await sv.get_user_chat_sessions(db, user.id)



@app.get("/chat/history")
async def get_chat_history(
    db: orm.Session = Depends(sv.get_db),
    user=Depends(sv.get_current_user),
):
    sessions_with_messages = await sv.get_chat_history_service(
        db=db,
        user=user
    )

    return [
        {
            "session_id": session.id,
            "created_at": session.created_at,
            "messages": [
                {
                    "id": m.id,
                    "sender": m.sender.value,
                    "message_text": m.message_text,
                    "is_emergency": m.is_emergency,
                    "created_at": m.created_at
                }
                for m in messages
            ]
        }
        for session, messages in sessions_with_messages
    ]