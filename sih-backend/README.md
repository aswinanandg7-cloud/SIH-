# SIH Backend — Booking & Verification Service

FastAPI backend service for agricultural slot booking and token verification.

## Prerequisites
- Python 3.9+

## Installation

1. Navigate to the backend directory:
   ```bash
   cd sih-backend
   ```

2. (Optional) Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Server

Start the FastAPI development server:
```bash
uvicorn main:app --reload --port 8000
```

- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Get Slots**: `GET http://localhost:8000/slots`
- **Book Slot**: `POST http://localhost:8000/book`
- **Verify Token**: `POST http://localhost:8000/verify/{token}`
