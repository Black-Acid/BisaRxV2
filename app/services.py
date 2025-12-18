import models
from database import Base, engine, SessionLocal
import schemas as sma
from sqlalchemy import orm
from passlib.context import CryptContext
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, security, Depends, status
import jwt
from uuid import UUID, uuid4
import httpx
from datetime import datetime, timedelta, timezone

AI_URL = "https://bisarx-assistant-1031993103540.us-central1.run.app/chat"
TIMEOUT = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = "akshduiheadnklasnid's/ekja"
ALGORITHM = "HS256"
oauth2schema = security.OAuth2PasswordBearer("/api/login")

def create_db():
    Base.metadata.create_all(bind=engine)
    

def get_db():
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()
        

async def create_user(user: sma.LoginRequest, db:orm.Session):
    hash_pwd = pwd_context.hash(user.password)
    
    try:
        new_user = models.UserModel(
            email=user.email,
            hashed_password=hash_pwd
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not save the user due to{e._message}")
    
    return new_user


    
async def create_token(user: models.UserModel):
    payload = {
        "sub": str(user.id), 
        "email": user.email,
        "is_active": user.is_active
    }
    
    token = jwt.encode(payload, JWT_SECRET)
    
    return dict(access_token=token, token_type="bearer")
    
    
async def get_user(user: sma.LoginRequest, db: orm.Session):
    return db.query(models.UserModel).filter_by(email=user.email ).first()

async def login(identifier: str, password: str, db: orm.Session):
    user = db.query(models.UserModel).filter_by(email=identifier).first()
    
    if not user:
        return False
    
    
    if not user.password_verification(password):
        return False
    
    return user


async def get_current_user(
    db: orm.Session = Depends(get_db),
    token: str = Depends(oauth2schema)
):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = db.query(models.UserModel).filter(
            models.UserModel.id == user_id
        ).first()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")

    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def medical_ai_response(user_message: str) -> tuple[str, bool]:
    """
    Temporary AI mock.
    Returns (answer, is_emergency)
    """
    emergency_keywords = ["chest pain", "bleeding", "unconscious", "seizure"]

    is_emergency = any(word in user_message.lower() for word in emergency_keywords)

    if is_emergency:
        return (
            "This may be a medical emergency. Please seek immediate medical attention.",
            True
        )

    return (
        "Based on your symptoms, it may be advisable to rest and consult a healthcare professional if symptoms persist.",
        False
    )


async def handle_chat(payload: sma.ChatRequest, db: orm.Session, user):
    """
    Handles saving user message, calling AI, saving AI response, 
    and returning structured response.
    """
    session = (
        db.query(models.ChatSessionModel)
        .filter_by(user_id=user.id, id=payload.session_id)
        .first()
    )

    if not session:
        session = models.ChatSessionModel(
            id=payload.session_id,
            user_id=user.id
        )
        db.add(session)
        db.commit()

    # Save user message
    user_msg = models.MessageModel(
        session_id=payload.session_id,
        sender= models.SenderType.USER,
        message_text=payload.message
    )
    db.add(user_msg)
    db.commit()

    # Call AI
    ai_text, is_emergency = medical_ai_response(payload.message)

    # Save AI message
    ai_msg = models.MessageModel(
        session_id=payload.session_id,
        sender=models.SenderType.AI,
        message_text=ai_text,
        is_emergency=is_emergency
    )
    db.add(ai_msg)
    db.commit()

    # Return structured response
    return {
        "session_id": payload.session_id,
        "user_message": payload.message,
        "ai_message": ai_text,
        "is_emergency": is_emergency
    }
    
async def get_user_chat_sessions(db: orm.Session, user_id) -> sma.ChatSessionsResponse:
    sessions = (
        db.query(models.ChatSessionModel)
        .filter(models.ChatSessionModel.user_id == user_id)
        .order_by(models.ChatSessionModel.created_at.desc())
        .all()
    )
    
    return sma.ChatSessionsResponse(
        sessions = [
            sma.ChatSessionsOut(
                id = s.id,
                session_title = s.session_title,
                is_closed=s.is_closed,
                created_at=s.created_at
            )
            for s in sessions
        ]
    )
    
    
    
async def get_chat_history_service(
    db: orm.Session,
    user: models.UserModel,
):
    sessions = (
        db.query(models.ChatSessionModel)
        .filter(models.ChatSessionModel.user_id == user.id)
        .order_by(models.ChatSessionModel.created_at.desc())
        .all()
    )

    result = []

    for session in sessions:
        messages = (
            db.query(models.MessageModel)
            .filter(models.MessageModel.session_id == session.id)
            .order_by(models.MessageModel.created_at.asc())
            .all()
        )

        result.append((session, messages))

    return result





SESSION_TIMEOUT = timedelta(minutes=5)

async def get_or_create_session(db: orm.Session, user_id: UUID):
    now = datetime.now(timezone.utc)

    session = (
        db.query(models.ChatSessionModel)
        .filter(
            models.ChatSessionModel.user_id == user_id,
            models.ChatSessionModel.is_closed.is_(False)
        )
        .order_by(models.ChatSessionModel.updated_at.desc())
        .first()
    )

    if session:
        # Check if the session has expired
        expired = (now - session.updated_at.replace(tzinfo=timezone.utc)) > SESSION_TIMEOUT
        if not expired:
            return session

        # Session expired → close it
        session.is_closed = True
        db.commit()

    # Create a new session
    new_session = models.ChatSessionModel(
        user_id=user_id
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session








async def call_medical_ai3(message: str, session_id: str) -> dict:
    """
    Calls the AI service with the session_id to maintain state
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            AI_URL,
            json={
                "session_id": str(session_id),
                "message": message
            }
        )

    data = response.json()
    # Ensure the AI service is responding correctly
    if "reply" not in data or "status" not in data:
        raise RuntimeError("Invalid response from AI service")

    return data


async def handle_chat4(payload: sma.ChatRequest, db: orm.Session, user):
    """
    Handles:
    - session lookup/creation
    - saving user message
    - calling AI service
    - saving AI response
    """

    # 1️⃣ Get or create ACTIVE session for user
    session = await get_or_create_session(db, user.id)
    session_id = session.id  # UUID object

    # 2️⃣ Save user message
    user_msg = models.MessageModel(
        session_id=session_id,
        sender=models.SenderType.USER,
        message_text=payload.message
    )
    db.add(user_msg)
    db.commit()  # commit BEFORE AI call (important)

    # 3️⃣ Call AI (NO DB TRANSACTION HELD)
    try:
        ai_response = await call_medical_ai3(
            payload.message,
            str(session_id)  # serialize for AI service
        )
        ai_text = ai_response["reply"]
        status = ai_response.get("status", "ongoing")
        is_emergency = status == "emergency"

    except Exception as e:
        print("AI ERROR:", repr(e))
        ai_text = (
            "I'm unable to process your request right now. "
            "Please try again later."
        )
        status = "ongoing"
        is_emergency = False

    # 4️⃣ Save AI response
    ai_msg = models.MessageModel(
        session_id=session_id,
        sender=models.SenderType.AI,
        message_text=ai_text,
        is_emergency=is_emergency
    )
    db.add(ai_msg)

    # 5️⃣ Final commit
    db.commit()

    return {
        "session_id": str(session_id),
        "user_message": payload.message,
        "ai_message": ai_text,
        "status": status,
        "is_emergency": is_emergency
    }
