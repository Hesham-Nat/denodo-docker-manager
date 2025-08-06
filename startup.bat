@echo off
echo Starting Denodo Docker Manager...


:: Step 1: Create virtual environment
python -m venv venv

:: Step 2: Activate environment
call venv\Scripts\activate

:: Step 3: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

:: Step 4: Install dependencies
echo Installing requirements...
pip install -r requirements.txt

:: Step 5: list of tags from google cloud
echo Pulling list of tags from google cloud...
call fetch_images.bat

:: Step 6: Start the FastAPI server
echo Launching web app at http://127.0.0.1:5665
uvicorn app.main:app --reload --port 5665
