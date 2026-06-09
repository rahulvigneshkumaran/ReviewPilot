from fastapi import HTTPException, status

class ReviewPilotException(Exception):
    """Base exception class for ReviewPilot domain logic errors."""
    pass

class CredentialsException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

class UserNotFoundException(HTTPException):
    def __init__(self, detail: str = "User not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )

class RepositoryNotFoundException(HTTPException):
    def __init__(self, detail: str = "Repository not found or access denied"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )

class ReviewNotFoundException(HTTPException):
    def __init__(self, detail: str = "Review not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )
