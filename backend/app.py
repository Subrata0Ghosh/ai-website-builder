from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from openai import OpenAI
import uuid
import zipfile
import os
import json
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi import Form
import re

# ----------------- DATABASE -----------------
DATABASE_URL = "sqlite:///./data.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    content = Column(Text)

Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



# Initialize app
app = FastAPI()

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI
client = OpenAI(api_key="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")

# Directory for generated projects
GENERATED_DIR = Path("generated_projects")
GENERATED_DIR.mkdir(exist_ok=True)

@app.post("/generate/")
async def generate_project(request: Request):
    """Generate a project folder with index.html + preview"""
    try:
        data = await request.json()
        description = data.get("description", "").strip()

        if not description:
            return JSONResponse({"error": "Missing project description"}, status_code=400)

        # Create unique folder
        project_id = str(uuid.uuid4())[:10]
        project_folder = GENERATED_DIR / project_id
        project_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"Generated pages for {project_id}:")
        for f in project_folder.iterdir():
            print(" -", f.name)
        
        
        # ---- AI Generation ----
        system_prompt = """
        You are an expert full-stack web developer.

        Your job: Generate a complete multi-page website using TailwindCSS and Vanilla JS.

        Rules:
        - Return HTML for multiple pages.
        - Each page must start with this exact line:
        ===PAGE: filename.html===
        - After that line, include full <html> code for that page.
        - Pages to include: index.html, login.html, signup.html, about.html, tasks.html.
        - Use TailwindCSS from CDN for modern, beautiful UI.
        - Do NOT include markdown, explanations, or code fences.
        """

        user_prompt = f"""
        Build a project based on this description: "{description}"

        Include all pages as instructed above.
        """

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )

        html_code = completion.choices[0].message.content.strip()

        
        # Remove unwanted Markdown/code-block markers if present
        html_code = html_code.replace("```html", "").replace("```", "")
        html_code = html_code.split("###")[0]  # Remove any explanations accidentally included


        if "<!DOCTYPE html>" in html_code:
            # --- Extract multiple pages if LLM used "PAGE:" markers ---
            matches = re.findall(
                r"=+\s*PAGE:\s*(.*?)=+\s*(<!DOCTYPE html[\s\S]*?)(?==+\s*PAGE:|$)",
                html_code
            )

            if matches:
                for filename, content in matches:
                    filename = filename.strip()
                    if not filename.endswith(".html"):
                        filename += ".html"

                    # Inject base tag so links work
                    base_tag = f'<base href="/generated_projects/{project_id}/" />'
                    if "<head>" in content:
                        content = content.replace("<head>", f"<head>{base_tag}")
                    else:
                        content = f"<head>{base_tag}</head>{content}"

                    (project_folder / filename).write_text(content.strip(), encoding="utf-8")
            else:
                # --- Auto-split single-page HTML into sections like login, signup, etc. ---
                sections = re.split(r"<!--\s*(PAGE|Section):\s*(.*?)\s*-->", html_code)
                if len(sections) > 1:
                    for i in range(1, len(sections), 3):
                        page_name = sections[i+1].strip().replace(" ", "_").lower()
                        page_html = sections[i+2]
                        filename = f"{page_name}.html"
                        (project_folder / filename).write_text(page_html.strip(), encoding="utf-8")
                else:
                    (project_folder / "index.html").write_text(html_code, encoding="utf-8")
        else:
            (project_folder / "index.html").write_text(html_code, encoding="utf-8")





        # Save index.html
        # html_file = project_folder / "index_preview.html"
        # html_file.write_text(html_code, encoding="utf-8")
        index_path = project_folder / "index.html"
        preview_path = project_folder / "index_preview.html"
        if index_path.exists():
            preview_path.write_text(index_path.read_text(), encoding="utf-8")

        # Zip project folder
        zip_path = GENERATED_DIR / f"{project_id}.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for file in project_folder.rglob("*"):
                zipf.write(file, file.relative_to(GENERATED_DIR))

        return JSONResponse({
            "project_id": project_id,
            "message": "Project generated successfully"
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    
@app.post("/api/signup")
async def signup(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    if db.query(User).filter(User.username == username).first():
        db.close()
        return {"success": False, "message": "Username already exists"}
    new_user = User(username=username, password=password)
    db.add(new_user)
    db.commit()
    db.close()
    return {"success": True, "message": "Signup successful!"}


@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username, User.password == password).first()
    db.close()
    if user:
        return {"success": True, "message": "Login successful!"}
    else:
        return {"success": False, "message": "Invalid credentials"}


@app.get("/api/tasks/{username}")
async def get_tasks(username: str):
    db = SessionLocal()
    tasks = db.query(Task).filter(Task.username == username).all()
    db.close()
    return [{"id": t.id, "content": t.content} for t in tasks]


@app.post("/api/tasks")
async def add_task(username: str = Form(...), content: str = Form(...)):
    db = SessionLocal()
    task = Task(username=username, content=content)
    db.add(task)
    db.commit()
    db.close()
    return {"success": True, "message": "Task added"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    db.close()
    return {"success": True, "message": "Task deleted"}


@app.get("/download/{project_id}.zip")
async def download_zip(project_id: str):
    zip_path = GENERATED_DIR / f"{project_id}.zip"
    if not zip_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(zip_path, media_type="application/zip", filename=f"{project_id}.zip")


@app.get("/generated_projects/{project_id}/{filename}")
async def get_generated_file(project_id: str, filename: str):
    """Serve any generated HTML or static asset from a project folder."""
    file_path = GENERATED_DIR / project_id / filename
    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    # Automatically set correct content type
    if filename.endswith(".html"):
        media_type = "text/html"
    elif filename.endswith(".css"):
        media_type = "text/css"
    elif filename.endswith(".js"):
        media_type = "application/javascript"
    else:
        media_type = "application/octet-stream"
    return FileResponse(file_path, media_type=media_type)

