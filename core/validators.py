import re
from datetime import datetime, date
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email
from PIL import Image, UnidentifiedImageError

INDIAN_MOBILE_REGEX = re.compile(r'^(\+91[\-\s]?|0)?[6-9]\d{9}$')
USERNAME_REGEX = re.compile(r'^[\w.@+-]+$')

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.txt', '.csv', '.docx'}


def validate_indian_mobile(phone_str):
    """
    Validates Indian mobile phone numbers.
    Accepts 10 digits starting with 6-9, with optional +91, 0, or space/hyphen formatting.
    Returns error message string if invalid, or None if valid.
    """
    if not phone_str:
        return None
    
    cleaned = str(phone_str).strip()
    # Check for disallowed characters (letters or invalid symbols)
    if any(c.isalpha() for c in cleaned):
        return "Mobile number must not contain letters. Please enter a valid 10-digit Indian mobile number."
    
    # Strip spaces, hyphens, and parentheses for regex matching
    stripped = re.sub(r'[\s\-\(\)]', '', cleaned)
    if not INDIAN_MOBILE_REGEX.match(stripped):
        return "Invalid mobile number format. Enter a valid 10-digit Indian mobile number (e.g., 9822011223 or +91 98220 11223)."
    
    return None


def validate_email_address(email_str):
    """
    Validates email format using Django's standard email validator.
    Returns error message string if invalid, or None if valid.
    """
    if not email_str:
        return None
    
    cleaned = str(email_str).strip()
    try:
        django_validate_email(cleaned)
        return None
    except ValidationError:
        return f"'{cleaned}' is not a valid email address. Please enter a valid email (e.g., user@example.com)."


def validate_username(username_str):
    """
    Validates username format and length.
    Returns error message string if invalid, or None if valid.
    """
    if not username_str:
        return "Username is required."
    
    cleaned = str(username_str).strip()
    if len(cleaned) < 3:
        return "Username must be at least 3 characters long."
    if len(cleaned) > 150:
        return "Username must not exceed 150 characters."
    if not USERNAME_REGEX.match(cleaned):
        return "Username can only contain letters, numbers, and @/./+/-/_ characters."
    
    return None


def validate_uploaded_image(uploaded_file, max_size=MAX_UPLOAD_SIZE):
    """
    Validates uploaded image file size, MIME type, and structural integrity.
    Returns error message string if invalid, or None if valid.
    """
    if not uploaded_file:
        return None
    if uploaded_file.size > max_size:
        return f"Image file size must not exceed {max_size // (1024 * 1024)} MB."
    if uploaded_file.content_type not in ALLOWED_IMAGE_TYPES:
        return "Only JPEG, PNG, and WEBP image files are allowed."
    
    try:
        image = Image.open(uploaded_file)
        image.verify()
    except (UnidentifiedImageError, OSError):
        return "The uploaded file is not a valid or readable image."
    finally:
        uploaded_file.seek(0)
    
    return None


def validate_uploaded_document(uploaded_file, max_size=MAX_UPLOAD_SIZE):
    """
    Validates attachment files (images, documents, PDFs).
    Raises ValidationError if invalid.
    """
    import os
    if not uploaded_file:
        return
    if uploaded_file.size > max_size:
        raise ValidationError(f"File size must not exceed {max_size // (1024 * 1024)} MB.")
    
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(f"Unsupported file type '{ext}'. Allowed types: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}.")


def validate_date_string(date_str, field_name="Date", allow_future=True):
    """
    Validates date string in YYYY-MM-DD format.
    Returns error message string if invalid, or None if valid.
    """
    if not date_str:
        return None
    
    try:
        parsed = datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return f"Invalid {field_name} format ('{date_str}'). Please use YYYY-MM-DD."
    
    if not allow_future and parsed > date.today():
        return f"{field_name} cannot be a future date."
    
    return None
