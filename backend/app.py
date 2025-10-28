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
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env
load_dotenv()

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

# Initialize client using key from environment
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# print(f"api key:{client}")

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
        
        
       
               # ---- AI Generation (JSON output enforced) ----
        system_prompt = """
        You are an expert full-stack web developer and a code-generation assistant.

        Your job: produce a multi-page website as a JSON object only. STRICT RULES:
        1) Output MUST be valid JSON and nothing else (no markdown, no explanation text).
        2) The top-level JSON must be an object with a key "files" that is an array of objects.
           Each file object must have: "path" (string, e.g. "index.html" or "assets/style.css")
           and "content" (string) containing the full file contents (HTML/CSS/JS).
        3) Include at least the following files (complete HTML with <!DOCTYPE html>):
           "index.html", "login.html", "signup.html", "about.html", "tasks.html".
        4) Use TailwindCSS from CDN where appropriate.
        5) Use relative links inside HTML (e.g., <a href="login.html">).
        6) Do NOT include any keys other than "files" at top-level.
        7) Keep JSON compact (but valid). If content contains characters that require escaping, ensure JSON remains valid.
        """

        user_prompt = f"""
        Build a project based on this description: {json.dumps(description)}

        Return a JSON object that matches the rules above. Example shape:
        {{
          "files": [
            {{ "path": "index.html", "content": "<!DOCTYPE html>... entire html ..." }},
            {{ "path": "login.html", "content": "<!DOCTYPE html>... entire html ..." }},
            ...
          ]
        }}
        """

        # Call the model (enforce deterministic low-temp)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            
        )

        raw = completion.choices[0].message.content.strip()

        # ---- Robust JSON extraction & parsing ----
        def extract_json(s: str):
            """
            Try to parse JSON directly. If it fails, attempt to find the largest JSON object substring.
            Returns parsed object or raises ValueError.
            """
            try:
                return json.loads(s)
            except Exception:
                # attempt to locate a {...} block with balanced braces (simple heuristic)
                # find the first '{' and last '}' and try to load progressively
                first = s.find("{")
                last = s.rfind("}")
                if first == -1 or last == -1 or last <= first:
                    raise ValueError("No JSON object found in model output.")
                candidate = s[first:last+1]
                # attempt incremental trimming of trailing invalid chars
                while candidate:
                    try:
                        return json.loads(candidate)
                    except Exception:
                        # chop off a small tail and try again
                        candidate = candidate[:-1]
                raise ValueError("Failed to extract valid JSON from model output.")

        try:
            parsed = extract_json(raw)
        except ValueError as e:
            # helpful debug info in logs and return an error to client
            print("MODEL OUTPUT (preview):", raw[:1000])
            raise RuntimeError("Failed to parse JSON from model output: " + str(e))

        # Validate structure
        if not isinstance(parsed, dict) or "files" not in parsed or not isinstance(parsed["files"], list):
            print("Parsed JSON doesn't contain expected 'files' array. Preview:", str(parsed)[:1000])
            raise RuntimeError("Model output JSON must contain a 'files' array.")

        # Write files to project folder
        for fileobj in parsed["files"]:
            if not isinstance(fileobj, dict) or "path" not in fileobj or "content" not in fileobj:
                continue
            rel_path = fileobj["path"].strip()
            # sanitize path: prevent directory traversal
            rel_path = rel_path.replace("..", "").lstrip("/")
            target = project_folder / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            content = fileobj["content"]
            # Inject base tag into HTML files so relative links work in iframe/preview
            if rel_path.endswith(".html"):
                # ensure the document has <head>
                base_tag = f'<base href="/generated_projects/{project_id}/" />'
                if "<head" in content.lower():
                    # replace first occurrence of <head.*?> with <head> + base_tag after tag
                    content = re.sub(r"(?i)(<head[^>]*>)", r"\1" + base_tag, content, count=1)
                else:
                    # prepend head with base
                    content = f"<head>{base_tag}</head>\n" + content
            target.write_text(content, encoding="utf-8")

        # Ensure index.html exists (fallback to first HTML file if not provided)
        if not (project_folder / "index.html").exists():
            # find first .html in folder
            for p in sorted(project_folder.rglob("*.html")):
                (project_folder / "index.html").write_text(p.read_text(), encoding="utf-8")
                break

       
       
    
       

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

