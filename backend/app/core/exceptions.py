from fastapi import HTTPException, status


class CustomHTTPException(HTTPException):
    """
    Base class for custom HTTP exceptions.
    Extend this class to create exceptions with a specific HTTP status code and message.
    """

    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


# Review-related exceptions
class InvalidReviewTypeException(CustomHTTPException):
    """
    Raised when an invalid review type is provided.
    """

    def __init__(self, review_type: str):
        detail = f"Invalid review type: '{review_type}'. Must be 'new' or 'past'."
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class IndustryNotFoundException(CustomHTTPException):
    """
    Raised when the requested industry is not found.
    """

    def __init__(self, industry_id: int):
        detail = f"Industry with ID {industry_id} not found."
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class FileUploadException(CustomHTTPException):
    """
    Raised when there is an error saving the uploaded file(s).
    """

    def __init__(self):
        detail = "Failed to save uploaded files."
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


class CombinationFailedException(CustomHTTPException):
    """
    Raised when combining Excel files fails to produce an output file.
    """

    def __init__(self):
        detail = "Combination failed, output file not found."
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


class CleaningFailedException(CustomHTTPException):
    """
    Raised when cleaning the combined file fails.
    """

    def __init__(self):
        detail = "Cleaning failed, output file not found."
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


class NoAPIKeyException(CustomHTTPException):
    """
    Raised when the OpenAI API key is missing from the user settings.
    """

    def __init__(self):
        detail = "No OpenAI API key found. Please add your API key in your account settings."
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ReviewNotFoundException(CustomHTTPException):
    """
    Raised when a requested review is not found in the database.
    """

    def __init__(self, review_id: int):
        detail = f"Review with ID {review_id} not found."
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


# Industry-related exceptions
class IndustryAlreadyExistsException(CustomHTTPException):
    """
    Raised when attempting to create an industry that already exists.
    """

    def __init__(self, industry_name: str):
        detail = f"Industry '{industry_name}' already exists."
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class CategoryAlreadyExistsException(CustomHTTPException):
    """
    Raised when attempting to create a category that already exists for an industry.
    """

    def __init__(self, category_name: str, industry_name: str):
        detail = f"Category '{category_name}' already exists for industry '{industry_name}'."
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


# User-related exceptions
class UserNotFoundException(CustomHTTPException):
    """
    Raised when a user is not found.
    """

    def __init__(self):
        detail = "User not found."
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UserDeletionException(CustomHTTPException):
    """
    Raised when there is an error deleting a user.
    """

    def __init__(self, error: str = None):
        detail = (
            f"An error occurred while deleting user: {error}"
            if error
            else "An error occurred while deleting user."
        )
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


class InvalidAPIKeyException(CustomHTTPException):
    """
    Raised when an invalid OpenAI API key is provided.
    """

    def __init__(self, error_msg: str = None):
        detail = (
            f"Invalid OpenAI API key: {error_msg}"
            if error_msg
            else "Invalid OpenAI API key."
        )
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class EmptyAPIKeyException(CustomHTTPException):
    """
    Raised when an empty API key is provided.
    """

    def __init__(self):
        detail = "API key cannot be empty."
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class APIKeyEncryptionException(CustomHTTPException):
    """
    Raised when there is an error encrypting the API key.
    """

    def __init__(self, error: str = None):
        detail = (
            f"Failed to encrypt API key: {error}"
            if error
            else "Failed to encrypt API key."
        )
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


class APIKeyUpdateException(CustomHTTPException):
    """
    Raised when there is an error updating the API key.
    """

    def __init__(self, error: str = None):
        detail = (
            f"An error occurred while updating API key: {error}"
            if error
            else "An error occurred while updating API key."
        )
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


# Index-related exceptions
class IndexNotFoundException(CustomHTTPException):
    """
    Raised when an index is not found.
    """

    def __init__(self, industry_id: int):
        detail = f"Index not found for industry with ID {industry_id}."
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class InvalidIndexModeException(CustomHTTPException):
    """
    Raised when an invalid index mode is provided.
    """

    def __init__(self, mode: str):
        detail = f"Invalid mode: '{mode}'. Must be 'add' or 'replace'."
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class IndexJobNotFoundException(CustomHTTPException):
    """
    Raised when an index job is not found.
    """

    def __init__(self, job_id: str):
        detail = f"Index job with ID {job_id} not found."
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class InvalidReviewSelectionException(CustomHTTPException):
    """
    Raised when an invalid review is selected for indexing.
    """

    def __init__(self):
        detail = "Selected review must be a cleaned past review."
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class WebSocketConnectionException(CustomHTTPException):
    """
    Raised when there is an error with the WebSocket connection.
    """

    def __init__(self, error: str = None):
        detail = (
            f"WebSocket connection error: {error}"
            if error
            else "WebSocket connection error."
        )
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )
