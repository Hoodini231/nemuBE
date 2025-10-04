from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from typing import List, Optional
import httpx
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")


@router.post("/get-story-board")
async def get_story_board(
    prompt: str = Form(...),
    panels: str = Form(...),
    style: str = Form(...),
    images: List[UploadFile] = File(...)
):
    """
    Endpoint to receive story prompt, panels, style, and images from frontend,
    then forward to n8n webhook for processing.
    """
    if not N8N_WEBHOOK_URL:
        raise HTTPException(
            status_code=500,
            detail="N8N webhook URL not configured. Please set N8N_WEBHOOK_URL in .env file"
        )

    try:
        # Prepare files for n8n webhook
        files = []
        for idx, image in enumerate(images):
            content = await image.read()
            files.append(
                ("images", (image.filename or f"image_{idx}.png", content, image.content_type))
            )

        # Prepare form data
        data = {
            "prompt": prompt,
            "panels": panels,
            "style": style
        }

        # Forward to n8n webhook
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                N8N_WEBHOOK_URL,
                data=data,
                files=files
            )

            # Check if request was successful
            response.raise_for_status()

            return {
                "status": "success",
                "message": "Story board request processed",
                "data": response.json() if response.content else None,
                "n8n_status_code": response.status_code
            }

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"n8n webhook error: {e.response.text}"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to n8n webhook: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )
