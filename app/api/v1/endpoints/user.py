
from fastapi import APIRouter, Depends, HTTPException, status, Response
from typing import List
from beanie import PydanticObjectId


from app.api.v1.schemas.user import UserCreate, UserRead, UserUpdate
from app.api.v1.schemas.auth import Token


from app.services.auth import AuthService
from app.services.user import UserService, get_user_service


from app.core.security import create_access_token


from app.schemas.user import User


from app.exceptions.user import UserNotFoundError, UserAlreadyExistsError, UnauthorizedError

from app.exceptions.base import AppException



async def get_current_active_user() -> User:



    user = await User.find_one(User.email == "test@example.com")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Dummy user not found for testing")

    return user




router = APIRouter(
    prefix="/users",
    tags=["Users"]
)




@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service)

):
    """
    Registers a new user and returns an access token.
    """
    try:


        created_user = await user_service.create_user(user_data.model_dump())

        token = create_access_token({"sub": str(created_user.id)})
        return {"access_token": token, "token_type": "bearer"}
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid user data: {e}")
    except Exception as e:

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during registration.")




@router.get("/me", response_model=UserRead)
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the details of the currently logged-in user.
    """


    return current_user

@router.put("/me", response_model=UserRead)
async def update_users_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    user_service: UserService = Depends(get_user_service)
):
    """
    Update the details of the currently logged-in user.
    """
    try:
        updated_user = await user_service.update_user(current_user.id, user_update)
        return updated_user
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ValueError as e:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid update data: {e}")
    except Exception as e:

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during update.")


@router.get("/{user_id}", response_model=UserRead)
async def read_user_by_id(
    user_id: PydanticObjectId,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user)

):
    """
    Get a specific user by their ID.
    (Requires authentication, potentially admin rights).
    """

    if not current_user.is_admin and current_user.id != user_id:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this user.")

    try:
        user = await user_service.get_user_by_id(user_id)
        return user
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get("/", response_model=List[UserRead])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user)

):
    """
    Get a list of users.
    (Requires authentication, typically admin rights).
    """
    if not current_user.is_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required.")

    users = await user_service.get_users(skip=skip, limit=limit)
    return users


@router.put("/{user_id}", response_model=UserRead)
async def update_user_by_id(
    user_id: PydanticObjectId,
    user_update: UserUpdate,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user)

):
    """
    Update a specific user by ID.
    (Requires authentication, typically admin rights).
    """
    if not current_user.is_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required.")

    try:
        updated_user = await user_service.update_user(user_id, user_update)
        return updated_user
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ValueError as e:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid update data: {e}")
    except Exception as e:

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during update.")


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_id(
    user_id: PydanticObjectId,
    user_service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user)

):
    """
    Delete a specific user by ID.
    (Requires authentication, typically admin rights).
    """





    if not current_user.is_admin:
         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required.")

    try:
        deleted = await user_service.delete_user(user_id)
        if not deleted:

             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found or deletion failed.")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Exception as e:

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during deletion.")



