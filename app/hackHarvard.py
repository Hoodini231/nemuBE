from fastapi import FastAPI, UploadFile, HTTPException
import subprocess
import os
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI()

@app.get("/process-image")
async def process_image(file: UploadFile):
    try:
        # Save the uploaded file temporarily
        file_location = f"/tmp/{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Execute the kumiko command
        command = ["python3", "kumiko", "-i", file_location, "--save-panels"]
        logging.info(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)

        # Check for errors
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error: {result.stderr}")

        return {"message": "Image processed successfully", "output": result.stdout}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Clean up the temporary file
        if os.path.exists(file_location):
            os.remove(file_location)
