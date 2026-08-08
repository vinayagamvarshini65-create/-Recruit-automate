"""
app.py
Recruitment Email Automation - Flask application entry point.

Run with:
    python app.py
Then open http://localhost:5000
"""
import os
import io
import csv
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    send_file, jsonify
)

import database as db
import documents
import emailer

app = Flask(__name__)
app.secret_key = "dev-secret-change-in-production"

db.init_db()


# ---------------------------------------------------------------- dashboard

@app.route("/")
def dashboard():
    candidate_stats = db.stats()
    recent_log = db.get_log(limit=8)
    return render_template(
        "dashboard.html",
        stats=candidate_stats,
        recent_log=recent_log,
        dry_run=emailer.is_dry_run(),
    )


# ---------------------------------------------------------------- candidates

@app.route("/candidates")
def candidates():
    status_filter = request.args.get("status", "all")
    rows = db.get_candidates(status_filter)
    return render_template("candidates.html", candidates=rows, status_filter=status_filter)


@app.route("/candidates/add", methods=["POST"])
def add_candidate():
    db.add_candidate(
        name=request.form["name"].strip(),
        email=request.form["email"].strip(),
        role=request.form.get("role", "").strip(),
        department=request.form.get("department", "").strip(),
        salary=request.form.get("salary", "").strip(),
        joining_date=request.form.get("joining_date", "").strip(),
    )
    flash(f"Added candidate {request.form['name']}", "success")
    return redirect(url_for("candidates"))


@app.route("/candidates/<int:candidate_id>/delete", methods=["POST"])
def delete_candidate(candidate_id):
    db.delete_candidate(candidate_id)
    flash("Candidate removed", "success")
    return redirect(url_for("candidates"))


@app.route("/candidates/<int:candidate_id>/document")
def download_document(candidate_id):
    candidate = db.get_candidate(candidate_id)
    if not candidate or not candidate.get("document_path"):
        flash("No document generated yet for this candidate", "error")
        return redirect(url_for("candidates"))
    return send_file(candidate["document_path"], as_attachment=True)


# ---------------------------------------------------------------- CSV upload

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    file = request.files.get("csv_file")
    if not file or file.filename == "":
        flash("Please choose a CSV file to upload", "error")
        return redirect(url_for("upload"))

    stream = io.StringIO(file.stream.read().decode("utf-8-sig"))
    reader = csv.DictReader(stream)

    # Normalize header names (case-insensitive, tolerate spaces)
    required = {"name", "email"}
    rows = []
    for raw_row in reader:
        norm = {k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in raw_row.items()}
        if not norm.get("name") or not norm.get("email"):
            continue
        rows.append(norm)

    if not rows:
        flash("No valid rows found. Make sure the CSV has 'name' and 'email' columns.", "error")
        return redirect(url_for("upload"))

    db.bulk_add_candidates(rows)
    flash(f"Imported {len(rows)} candidates successfully", "success")
    return redirect(url_for("candidates"))


@app.route("/upload/sample")
def download_sample_csv():
    path = os.path.join(os.path.dirname(__file__), "sample_data", "candidates_sample.csv")
    return send_file(path, as_attachment=True, download_name="candidates_sample.csv")


# ---------------------------------------------------------------- templates

@app.route("/templates")
def templates_page():
    return render_template("templates_editor.html", templates=db.get_templates())


@app.route("/templates/<int:template_id>/save", methods=["POST"])
def save_template(template_id):
    db.save_template(
        template_id,
        name=request.form["name"].strip(),
        subject=request.form.get("subject", "").strip(),
        body=request.form["body"],
    )
    flash("Template saved", "success")
    return redirect(url_for("templates_page"))


# ---------------------------------------------------------------- generate & send

@app.route("/process", methods=["GET"])
def process_page():
    rows = db.get_candidates("pending")
    doc_template = db.get_templates("document")[0] if db.get_templates("document") else None
    email_template = db.get_templates("email")[0] if db.get_templates("email") else None
    return render_template(
        "process.html",
        candidates=rows,
        doc_template=doc_template,
        email_template=email_template,
        dry_run=emailer.is_dry_run(),
    )


@app.route("/process/preview/<int:candidate_id>")
def preview_candidate(candidate_id):
    candidate = db.get_candidate(candidate_id)
    doc_templates = db.get_templates("document")
    email_templates = db.get_templates("email")
    if not candidate or not doc_templates or not email_templates:
        return jsonify({"error": "Missing candidate or templates"}), 400

    doc_t = doc_templates[0]
    email_t = email_templates[0]

    merged_doc = documents.merge_fields(doc_t["body"], candidate)
    merged_subject = documents.merge_fields(email_t["subject"], candidate)
    merged_body = documents.merge_fields(email_t["body"], candidate)
    missing = documents.missing_fields(doc_t["body"], candidate) + documents.missing_fields(email_t["body"], candidate)

    return jsonify({
        "document_preview": merged_doc,
        "email_subject": merged_subject,
        "email_body": merged_body,
        "missing_fields": sorted(set(missing)),
    })


@app.route("/process/run", methods=["POST"])
def run_process():
    candidate_ids = request.form.getlist("candidate_ids")
    doc_templates = db.get_templates("document")
    email_templates = db.get_templates("email")

    if not doc_templates or not email_templates:
        flash("No templates configured", "error")
        return redirect(url_for("process_page"))

    doc_t = doc_templates[0]
    email_t = email_templates[0]

    processed, failed = 0, 0

    for cid in candidate_ids:
        candidate = db.get_candidate(int(cid))
        if not candidate:
            continue
        try:
            pdf_path = documents.generate_pdf(
                candidate, doc_t["body"], doc_title=doc_t["name"]
            )
            db.log_event(candidate["id"], "generate", "success", os.path.basename(pdf_path))

            success, detail = emailer.send_email(
                candidate, email_t["subject"], email_t["body"], attachment_path=pdf_path
            )
            db.log_event(candidate["id"], "send", "success" if success else "failed", detail)

            if success:
                db.update_candidate_status(candidate["id"], "sent", document_path=pdf_path)
                processed += 1
            else:
                db.update_candidate_status(candidate["id"], "failed", error_message=detail)
                failed += 1
        except Exception as e:
            db.log_event(candidate["id"], "generate", "failed", str(e))
            db.update_candidate_status(candidate["id"], "failed", error_message=str(e))
            failed += 1

    msg = f"Processed {processed} candidate(s) successfully."
    if failed:
        msg += f" {failed} failed - check the activity log."
    flash(msg, "success" if not failed else "error")
    return redirect(url_for("candidates"))


@app.route("/log")
def log_page():
    return render_template("log.html", log=db.get_log(limit=300))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
