from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_db_connection
from app.modules.auth import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, verify_password

# Initialize limiter for this router, or use a shared one.
# For simplicity, we create a local one here, but it's better to share it from main.
# We will just import the limiter we'll define in main or define it here and import in main.
# Let's define the limiter instance in main and import it here.
# Wait, circular import risk. Let's create a dependencies file or just define it here.
# Actually, slowapi limiter can be defined in a new file, or just in auth.py
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

@router.post("/token")
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (form_data.username,))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    from fastapi.responses import JSONResponse
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer", "message": "Login berhasil"})
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
    )
    return response

@router.post("/logout")
async def logout():
    from fastapi.responses import JSONResponse
    response = JSONResponse(content={"message": "Logout berhasil"})
    response.delete_cookie("access_token")
    return response
