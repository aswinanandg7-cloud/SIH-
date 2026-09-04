import sys
import os
from fastapi import FastAPI

# Add the backend directory to the python path so we can import it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sih-backend'))

from main import app as original_app

# Vercel's Python builder automatically exposes the app on the /api route.
# We mount the original app under /api so that internal routing like /book works.
app = FastAPI()
app.mount("/api", original_app)
