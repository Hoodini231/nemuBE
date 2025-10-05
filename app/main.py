import base64
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import os
import sys
from app.routers import n8n_processor
import json
import httpx
from typing import List, Optional
from fastapi import File, Form, UploadFile


app = FastAPI()

# CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# app.include_router(n8n_processor.router, prefix="/api", tags=["n8n"])

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

# Dynamic path configuration
KUMIKO_PATH = os.getenv("KUMIKO_PATH", "/Users/shaun/Documents/kumiko/kumiko")
TEST_IMAGE_PATH = os.getenv("TEST_IMAGE_PATH", "test.png")

async def process_image_with_kumiko(image_data, image_source="bytes"):
    """
    Process image with Kumiko to extract panels and coordinates
    Returns complete panel information for frontend
    """
    try:
        import uuid
        import base64
        import shutil
        import tempfile

        # Save image for Kumiko processing
        temp_image_path = f"temp_storyboard_{uuid.uuid4().hex}.png"

        # Fetch/decode image based on source
        if image_source == "url":
            async with httpx.AsyncClient() as client:
                img_response = await client.get(image_data)
                img_response.raise_for_status()
                image_bytes = img_response.content
        elif image_source == "base64":
            if image_data.startswith("data:image"):
                image_data = image_data.split(",")[1]
            image_bytes = base64.b64decode(image_data)
        else:
            image_bytes = image_data

        # Save image locally
        with open(temp_image_path, 'wb') as f:
            f.write(image_bytes)

        # Create output directory for panels
        panel_output_dir = tempfile.mkdtemp(prefix="kumiko_panels_")

        # Process with Kumiko
        kumiko_path = os.path.abspath(KUMIKO_PATH)
        python_executable = sys.executable
        command = [python_executable, kumiko_path, "-i", temp_image_path, "--save-panels", panel_output_dir]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            return {"error": f"Kumiko processing failed: {result.stderr}"}

        # Parse Kumiko JSON output
        stdout_lines = result.stdout.strip().split('\n')
        json_output = stdout_lines[0]
        kumiko_json = json.loads(json_output)

        # Get panel data from Kumiko
        size = kumiko_json[0]['size']
        panel_coordinates = kumiko_json[0]['panels']

        # Kumiko saves panels in nested directory
        image_basename = os.path.basename(temp_image_path)
        nested_panel_dir = os.path.join(panel_output_dir, image_basename)

        if not os.path.exists(nested_panel_dir):
            return {"error": f"Kumiko output directory not found: {nested_panel_dir}"}

        # Get panel image files
        all_files = os.listdir(nested_panel_dir)
        panels_generated = [f for f in all_files if os.path.isfile(os.path.join(nested_panel_dir, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        panels_generated.sort()

        # Convert panel images to base64
        panel_images = []
        for panel_file in panels_generated:
            panel_path = os.path.join(nested_panel_dir, panel_file)
            with open(panel_path, 'rb') as f:
                panel_bytes = f.read()
                panel_base64 = base64.b64encode(panel_bytes).decode('utf-8')
                ext = panel_file.lower().split('.')[-1]
                mime_type = 'image/jpeg' if ext in ['jpg', 'jpeg'] else 'image/png'
                panel_images.append(f"data:{mime_type};base64,{panel_base64}")
        
        image_data = base64.b64encode(image_bytes).decode('utf-8')
        image_data = f"data:image/png;base64,{image_data}"

        # Clean up temp files
        os.remove(temp_image_path)
        shutil.rmtree(panel_output_dir, ignore_errors=True)

        print(f"✅ Kumiko: Extracted {len(panel_images)} panels from image")

        return {
            "panels": panel_images,
            "coordinates": panel_coordinates,
            "total_size": size,
            "panel_count": len(panels_generated),
            "original_image": image_data,
        }

    except Exception as e:
        print(f"❌ Kumiko error: {type(e).__name__} - {str(e)}")
        return {"error": str(e)}

@app.post("/api/get-story-board")
async def get_story_board(
    prompt: str = Form(...),
    panels: str = Form(...),
    style: str = Form(...),
    illustration_images: List[UploadFile] = File(default=[]),
    character_images: List[UploadFile] = File(default=[]),
    character_names: List[str] = Form(default=[])
):
    """
    Endpoint to receive story prompt, panels, style, and images from frontend,
    then forward to n8n webhook for processing.

    Args:
        prompt: Story description
        panels: Number of panels (1-12)
        style: Art style (shonen/shojo/chibi/ink-wash)
        illustration_images: Reference images for art style/context
        character_images: Character reference images
        character_names: Names for each character (matches character_images)
    """
    # Validate style
    valid_styles = ["shonen", "shojo", "chibi", "ink-wash"]
    if style not in valid_styles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid style. Must be one of: {', '.join(valid_styles)}"
        )

    # Validate panels range
    try:
        panels_int = int(panels)
        if not 1 <= panels_int <= 12:
            raise HTTPException(
                status_code=400,
                detail="Panels must be between 1 and 12"
            )
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Panels must be a valid integer"
        )

    # Validate character names match character images (allow empty names)
    if len(character_names) > len(character_images):
        raise HTTPException(
            status_code=400,
            detail="Cannot have more character names than character images"
        )

    print(f"📨 Request: {panels} panels, {style} style, {len(illustration_images)} refs, {len(character_images)} chars")

    if not N8N_WEBHOOK_URL:
        raise HTTPException(
            status_code=500,
            detail="N8N webhook URL not configured. Please set N8N_WEBHOOK_URL in .env file"
        )

    try:
        # Prepare files for n8n webhook
        files = []

        # Add illustration images
        for idx, image in enumerate(illustration_images):
            content = await image.read()
            files.append(
                ("illustration_images", (image.filename or f"illustration_{idx}.png", content, image.content_type))
            )

        # Add character images
        for idx, image in enumerate(character_images):
            content = await image.read()
            files.append(
                ("character_images", (image.filename or f"character_{idx}.png", content, image.content_type))
            )

        # Prepare form data
        data = {
            "prompt": prompt,
            "panels": str(panels),
            "style": style
        }

        # Add character names to form data - maintain list structure for n8n
        names = []
        for name in character_names:
            names.append(name)
        data["character_names"] = names

        # Forward to n8n webhook
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                N8N_WEBHOOK_URL,
                data=data,
                files=files
            )
            response.raise_for_status()

            # Check if response is JSON or binary image
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                n8n_data = response.json()
            elif 'image/' in content_type:
                n8n_data = {"binary_image": True}
            else:
                try:
                    n8n_data = response.json()
                except:
                    n8n_data = {"binary_image": True}

            # Extract image from n8n response
            image_to_process = None
            image_source = None

            if n8n_data.get("binary_image"):
                image_to_process = response.content
                image_source = "bytes"
            elif "image_url" in n8n_data:
                image_to_process = n8n_data["image_url"]
                image_source = "url"
            elif "image" in n8n_data:
                if isinstance(n8n_data["image"], str) and n8n_data["image"].startswith("http"):
                    image_to_process = n8n_data["image"]
                    image_source = "url"
                elif isinstance(n8n_data["image"], str):
                    image_to_process = n8n_data["image"]
                    image_source = "base64"
            elif "result" in n8n_data:
                if isinstance(n8n_data["result"], str):
                    if n8n_data["result"].startswith("http"):
                        image_to_process = n8n_data["result"]
                        image_source = "url"
                    else:
                        image_to_process = n8n_data["result"]
                        image_source = "base64"
            elif "data" in n8n_data:
                image_to_process = n8n_data["data"]
                image_source = "base64"
            elif "output" in n8n_data:
                image_to_process = n8n_data["output"]
                image_source = "base64"

            if not image_to_process:
                return {
                    "status": "error",
                    "message": "n8n response received but no image data found",
                    "n8n_data": n8n_data
                }

            # Process image with Kumiko
            kumiko_result = await process_image_with_kumiko(image_to_process, image_source)

            if kumiko_result.get("error"):
                return {
                    "status": "error",
                    "message": "Story board generated but Kumiko processing failed",
                    "n8n_data": n8n_data,
                    "error": kumiko_result["error"]
                }

            # Return complete panel information to frontend
            print(f"✅ Success: Generated {kumiko_result['panel_count']} panels")
            return {
                "status": "success",
                "message": "Story board generated and processed successfully",
                "n8n_data": n8n_data,
                "final_image": kumiko_result["original_image"],
                "panels": kumiko_result["panels"],
                "coordinates": kumiko_result["coordinates"],
                "total_size": kumiko_result["total_size"],
                "panel_count": kumiko_result["panel_count"],
                "n8n_status_code": response.status_code
            }

    except httpx.HTTPStatusError as e:
        print(f"❌ n8n HTTP error: {e.response.status_code}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"n8n webhook error: {e.response.text}"
        )
    except httpx.RequestError as e:
        print(f"❌ Connection error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to n8n webhook: {str(e)}"
        )
    except Exception as e:
        print(f"❌ Error: {type(e).__name__} - {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

@app.get("/process-image")
async def process_image():
    try:
        # Use dynamic kumiko path
        kumiko_path = os.path.abspath(KUMIKO_PATH)
        
        # Check if kumiko exists
        if not os.path.exists(kumiko_path):
            raise HTTPException(
                status_code=500, 
                detail=f"Kumiko not found at {kumiko_path}. Please set KUMIKO_PATH environment variable or place kumiko in the default location."
            )
        
        # Execute the kumiko command to subdivide the panels
        command = ["python3", kumiko_path, "-i", TEST_IMAGE_PATH, "--save-panels"]
        result = subprocess.run(command, capture_output=True, text=True)

        # Check for errors
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error: {result.stderr}")
        
        # Parse the JSON output
        output_json = json.loads(result.stdout)

        # Dynamic output directory based on kumiko location
        output_dir = os.path.join(os.path.dirname(kumiko_path), "out", "panels")
        if not os.path.exists(output_dir):
            raise HTTPException(status_code=500, detail="Output directory does not exist")

        panels_generated = os.listdir(output_dir)
        panels = [panel for panel in panels_generated if os.path.isfile(os.path.join(output_dir, panel))]
        panels.sort()  # Ensure consistent order

        # Extract relevant information for panel sizing and positions
        size = output_json[0]['size']
        panelData = output_json[0]['panels']

        # Push the panels onto blank canvases to integrate with imageMagick psd later
        for i in range(0, len(panels)):
            command = ["magick", os.path.join(output_dir, panels[i]), f"panel{i}.png"]
            result = subprocess.run(command, capture_output=True, text=True)
            # Ensure the file is written before proceeding
            command = ["magick", "-size", f"{size[0]}x{size[1]}", "canvas:none", "-compose", "over", f"panel{i}.png", "-geometry", f"+{panelData[i][0]}+{panelData[i][1]}", "-composite", f"formatted_panel{i}.png"]
            result = subprocess.run(command, capture_output=True, text=True)
        
        # potentially run our segmentation model here?

        # aggregate into .psd file for modularity
        print ("Creating PSD file with panels:", panels)
        psd_command = (
            "magick " +
            " ".join([f"formatted_panel{i}.png" for i in range(len(panels))]) +
            " \( -clone 0,1 -flatten \) -insert 0 output_psd.psd"
        )

        # Execute the PSD creation command
        result = subprocess.run(psd_command, shell=True, capture_output=True, text=True)

        # Check for errors in the PSD creation command
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"PSD Creation Error: {result.stderr}")
        
        return {"message": "Image processed and PSD created successfully", "size": size, "panels": panels}

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse JSON output from kumiko.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
