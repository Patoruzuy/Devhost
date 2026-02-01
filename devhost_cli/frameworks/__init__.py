"""Framework-specific wrappers for Devhost runner"""

from .django import run_django
from .fastapi import run_fastapi
from .flask import run_flask

__all__ = ["run_flask", "run_fastapi", "run_django"]
