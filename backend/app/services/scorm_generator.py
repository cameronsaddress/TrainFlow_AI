import os
import shutil
import zipfile
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from sqlalchemy.orm import Session
from ..models.knowledge import TrainingCurriculum, VideoCorpus

# SCORM 1.2 Boilerplate API Adapter (Simplified)
SCORM_API_WRAPPER = """
var API = null;

function findAPI(win) {
    while ((win.API == null) && (win.parent != null) && (win.parent != win)) {
        win = win.parent;
    }
    API = win.API;
}

function init() {
    findAPI(window);
    if ((API == null) && (window.opener != null) && (typeof(window.opener) != "undefined")) {
        findAPI(window.opener);
    }
    if (API != null) {
        API.LMSInitialize("");
        var status = API.LMSGetValue("cmi.core.lesson_status");
        if (status == "not attempted") {
            API.LMSSetValue("cmi.core.lesson_status", "incomplete");
        }
    }
}

function reportScore(score, maxScore, status) {
    if (API != null) {
        API.LMSSetValue("cmi.core.score.raw", score);
        API.LMSSetValue("cmi.core.score.max", maxScore);
        API.LMSSetValue("cmi.core.score.min", 0);
        API.LMSSetValue("cmi.core.lesson_status", status);
        API.LMSCommit("");
    }
}

function finish() {
    if (API != null) {
        API.LMSFinish("");
    }
}
"""

class ScormGenerator:
    def __init__(self, db: Session, base_path: str = "/app/data/temp_exports"):
        self.db = db
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def generate_scorm_package(self, curriculum_id: int) -> str:
        # 1. Fetch Data
        curriculum = self.db.query(TrainingCurriculum).filter(TrainingCurriculum.id == curriculum_id).first()
        if not curriculum:
            raise ValueError("Curriculum not found")
        
        course_data = curriculum.structured_json
        
        # 2. Setup Build Dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join([c for c in curriculum.title if c.isalnum() or c in (' ', '_')]).rstrip().replace(" ","_")
        build_dir = os.path.join(self.base_path, f"scorm_{curriculum_id}_{timestamp}")
        content_dir = os.path.join(build_dir, "content")
        assets_dir = os.path.join(build_dir, "assets")
        
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
        os.makedirs(content_dir)
        os.makedirs(assets_dir)
        
        # 3. Create Manifest
        self._create_manifest(build_dir, curriculum, course_data)
        
        # 4. Create JS Wrapper
        with open(os.path.join(build_dir, "scorm_api_wrapper.js"), "w") as f:
            f.write(SCORM_API_WRAPPER)
            
        # 5. Process Modules & Lessons
        video_map = {} # cache video paths to avoid re-copying if reused
        
        modules = course_data.get("modules", [])
        for m_idx, module in enumerate(modules):
            lessons = module.get("lessons", [])
            for l_idx, lesson in enumerate(lessons):
                self._create_lesson_page(
                    content_dir=content_dir,
                    assets_dir=assets_dir,
                    lesson=lesson,
                    lesson_id=f"M{m_idx+1}_L{l_idx+1}",
                    video_map=video_map
                )

        # 6. Zip It
        zip_path = os.path.join(self.base_path, f"{safe_title}_SCORM1.2.zip")
        self._zip_directory(build_dir, zip_path)
        
        # Cleanup Buil Dir
        shutil.rmtree(build_dir)
        
        return zip_path

    def _create_manifest(self,  build_dir: str, curriculum: TrainingCurriculum, data: dict):
        root = ET.Element("manifest", {
            "identifier": f"TrainFlow_Course_{curriculum.id}",
            "version": "1.0",
            "xmlns": "http://www.imsproject.org/xsd/imscp_rootv1p1p2",
            "xmlns:adlcp": "http://www.adlnet.org/xsd/adlcp_rootv1p2",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": "http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd http://www.imsproject.org/xsd/imscp_rootv1p1p2 imsmd_rootv1p2p1.xsd http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd"
        })
        
        organizations = ET.SubElement(root, "organizations", {"default": "default_org"})
        org = ET.SubElement(organizations, "organization", {"identifier": "default_org"})
        ET.SubElement(org, "title").text = curriculum.title
        
        resources = ET.SubElement(root, "resources")
        
        # Iterate Hierarchy
        modules = data.get("modules", [])
        for m_idx, module in enumerate(modules):
            # Module Item (Folder-like)
            mod_item = ET.SubElement(org, "item", {"identifier": f"item_mod_{m_idx}"})
            ET.SubElement(mod_item, "title").text = f"Module {m_idx+1}: {module.get('title')}"
            
            lessons = module.get("lessons", [])
            for l_idx, lesson in enumerate(lessons):
                lesson_id = f"M{m_idx+1}_L{l_idx+1}"
                res_id = f"resource_{lesson_id}"
                file_href = f"content/lesson_{lesson_id}.html"
                
                # Lesson Item (Leaf)
                less_item = ET.SubElement(mod_item, "item", {
                    "identifier": f"item_{lesson_id}",
                    "identifierref": res_id
                })
                ET.SubElement(less_item, "title").text = lesson.get("title", f"Lesson {l_idx+1}")
                
                # Resource Definition
                res = ET.SubElement(resources, "resource", {
                    "identifier": res_id,
                    "type": "webcontent",
                    "href": file_href,
                    "adlcp:scormtype": "sco"
                })
                ET.SubElement(res, "file", {"href": file_href})
        
        # Write XML
        tree = ET.ElementTree(root)
        tree.write(os.path.join(build_dir, "imsmanifest.xml"), encoding="UTF-8", xml_declaration=True)

    def _create_lesson_page(self, content_dir: str, assets_dir: str, lesson: dict, lesson_id: str, video_map: dict):
        # 1. Resolve Video
        video_filename = lesson.get("video_filename")
        video_src = ""
        
        if video_filename:
            # Check DB for path
            video_rec = self.db.query(VideoCorpus).filter(VideoCorpus.filename == video_filename).first()
            if video_rec and video_rec.file_path and os.path.exists(video_rec.file_path):
                # Copy Video
                dest_name = f"video_{lesson_id}.mp4"
                dest_path = os.path.join(assets_dir, dest_name)
                shutil.copy2(video_rec.file_path, dest_path)
                video_src = f"../assets/{dest_name}"
        
        # 2. Extract Quiz Data
        quiz_data = lesson.get("quiz", {})
        questions = quiz_data.get("questions", []) if quiz_data else []
        has_quiz = len(questions) > 0
        quiz_json = json.dumps(questions)

        # 3. Build HTML
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{lesson.get('title')}</title>
    <script src="../scorm_api_wrapper.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: white; padding: 40px; line-height: 1.6; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        h1 {{ color: #60a5fa; margin-bottom: 10px; }}
        .objective {{ color: #94a3b8; font-size: 1.1em; margin-bottom: 30px; }}
        
        .video-wrapper {{ border: 1px solid #334155; border-radius: 12px; overflow: hidden; margin-bottom: 40px; background: #000; }}
        video {{ width: 100%; display: block; }}
        
        .section-title {{ font-size: 1.5em; font-weight: bold; margin-bottom: 20px; color: #e2e8f0; border-bottom: 2px solid #334155; padding-bottom: 10px; }}
        
        .summary {{ background: #1e293b; padding: 25px; border-radius: 12px; border-left: 4px solid #3b82f6; margin-bottom: 40px; }}
        
        .quiz-container {{ background: #1e293b; padding: 30px; border-radius: 12px; border: 1px solid #334155; }}
        .question {{ margin-bottom: 30px; padding-bottom: 20px; border-bottom: 1px solid #334155; }}
        .question:last-child {{ border-bottom: none; }}
        .q-text {{ font-weight: bold; font-size: 1.1em; margin-bottom: 15px; color: #fff; }}
        .options label {{ display: block; padding: 10px 15px; margin-bottom: 8px; background: #334155; border-radius: 6px; cursor: pointer; transition: all 0.2s; }}
        .options label:hover {{ background: #475569; }}
        .options input {{ margin-right: 10px; }}
        
        #submit-btn {{ background: #22c55e; color: white; border: none; padding: 12px 30px; font-size: 1.1em; font-weight: bold; border-radius: 8px; cursor: pointer; display: block; width: 100%; margin-top: 20px; }}
        #submit-btn:hover {{ background: #16a34a; }}
        
        .result {{ margin-top: 20px; padding: 20px; border-radius: 8px; text-align: center; font-weight: bold; display: none; }}
        .pass {{ background: #064e3b; color: #4ade80; border: 1px solid #059669; }}
        .fail {{ background: #450a0a; color: #f87171; border: 1px solid #dc2626; }}
    </style>
</head>
<body onload="init()" onunload="finish()">
    <div class="container">
        <h1>{lesson.get('title')}</h1>
        <p class="objective">{lesson.get('learning_objective')}</p>
        
        <div class="video-wrapper">
            {'<video controls onended="videoEnded()"><source src="' + video_src + '" type="video/mp4">Browser does not support video.</video>' if video_src else '<p>No Video Available.</p>'}
        </div>
        
        <div class="summary">
            <div class="section-title">Key Takeaways</div>
            <p>{lesson.get('summary_text', 'No summary provided.')}</p>
        </div>

        {f'''
        <div class="quiz-container" id="quiz-block">
            <div class="section-title">Knowledge Check</div>
            <form id="quiz-form">
                <div id="questions-render"></div>
                <button type="button" id="submit-btn" onclick="gradeQuiz()">Submit Answers</button>
            </form>
            <div id="result-box" class="result"></div>
        </div>
        ''' if has_quiz else ''}
    </div>

    <script>
        var hasQuiz = {str(has_quiz).lower()};
        var quizQuestions = {quiz_json};
        
        function videoEnded() {{
            // Use existing API wrapper
             // If there is no quiz, we complete on video end
            if (!hasQuiz) {{
                reportScore(100, 100, "completed");
            }}
        }}

        if (hasQuiz) {{
            var container = document.getElementById("questions-render");
            quizQuestions.forEach((q, idx) => {{
                var qDiv = document.createElement("div");
                qDiv.className = "question";
                
                var qTitle = document.createElement("div");
                qTitle.className = "q-text";
                qTitle.innerText = (idx + 1) + ". " + q.question;
                qDiv.appendChild(qTitle);
                
                var optDiv = document.createElement("div");
                optDiv.className = "options";
                
                q.options.forEach((opt, oIdx) => {{
                    var label = document.createElement("label");
                    var radio = document.createElement("input");
                    radio.type = "radio";
                    radio.name = "q_" + idx;
                    radio.value = opt; // Using text value to match correct_answer
                    
                    label.appendChild(radio);
                    label.appendChild(document.createTextNode(opt));
                    optDiv.appendChild(label);
                }});
                
                qDiv.appendChild(optDiv);
                container.appendChild(qDiv);
            }});
        }}

        function gradeQuiz() {{
            if (!hasQuiz) return;
            
            var score = 0;
            var total = quizQuestions.length;
            
            quizQuestions.forEach((q, idx) => {{
                var selected = document.querySelector('input[name="q_' + idx + '"]:checked');
                if (selected && selected.value === q.correct_answer) {{
                    score++;
                }}
            }});
            
            var percent = Math.round((score / total) * 100);
            var passed = percent >= 80;
            
            var resultBox = document.getElementById("result-box");
            resultBox.style.display = "block";
            resultBox.className = "result " + (passed ? "pass" : "fail");
            resultBox.innerHTML = "Score: " + percent + "% (" + score + "/" + total + ")<br>" + (passed ? "PASSED - Course Completed" : "FAILED - Please Review and Retry");
            
            // Report to LMS
            var status = passed ? "passed" : "failed";
            // In SCORM 1.2 "passed" implies completed, but some LMSs prefer "completed"
            // We'll set completed if passed
            var lessonStatus = passed ? "passed" : "incomplete";
            
            reportScore(percent, 100, lessonStatus);
            
            // Disable inputs
            var inputs = document.querySelectorAll("input");
            inputs.forEach(i => i.disabled = true);
            document.getElementById("submit-btn").style.display = "none";
        }}
    </script>
</body>
</html>"""

        with open(os.path.join(content_dir, f"lesson_{lesson_id}.html"), "w") as f:
            f.write(html_content)

    def _zip_directory(self, src_path, dest_zip):
        with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(src_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, src_path)
                    zf.write(file_path, arcname)
