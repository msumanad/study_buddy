import os
import uuid
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.utils import secure_filename

from app import login_manager
from app.models import User
from app.services.rag_service import RAGService


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def register_routes(app):
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("user_dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()

            if not user or not user.check_password(password):
                flash("Invalid username or password.", "danger")
                return render_template("login.html")

            login_user(user)
            flash("Logged in successfully.", "success")
            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("user_dashboard"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/admin")
    @login_required
    def admin_dashboard():
        if current_user.role != "admin":
            flash("Access denied.", "danger")
            return redirect(url_for("user_dashboard"))

        rag_service = RAGService(app)
        documents = rag_service.list_documents()
        return render_template("admin_dashboard.html", documents=documents)

    @app.route("/admin/upload", methods=["POST"])
    @login_required
    def upload_document():
        if current_user.role != "admin":
            flash("Only admins can upload files.", "danger")
            return redirect(url_for("user_dashboard"))

        file = request.files.get("file")
        subject = request.form.get("subject", "").strip()

        if not file or file.filename == "":
            flash("Please choose a file to upload.", "danger")
            return redirect(url_for("admin_dashboard"))

        if not subject:
            flash("Subject is required.", "danger")
            return redirect(url_for("admin_dashboard"))

        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in {".pdf", ".doc", ".docx"}:
            flash("Only PDF and document files are allowed.", "danger")
            return redirect(url_for("admin_dashboard"))

        upload_dir = app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)
        storage_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(upload_dir, storage_filename)
        file.save(file_path)

        try:
            rag_service = RAGService(app)
            rag_service.ingest_document(file_path=file_path, subject=subject, original_filename=filename, uploaded_by=current_user.id)
            flash("Document uploaded and indexed successfully.", "success")
        except Exception as exc:
            app.logger.exception("Document upload failed for %s", filename)
            if os.path.exists(file_path):
                os.remove(file_path)
            flash(f"Document upload failed: {exc}", "danger")

        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/delete", methods=["POST"])
    @login_required
    def delete_document():
        if current_user.role != "admin":
            flash("Only admins can delete files.", "danger")
            return redirect(url_for("user_dashboard"))

        document_id = request.form.get("document_id", "").strip()
        if not document_id:
            flash("Missing document ID for deletion.", "danger")
            return redirect(url_for("admin_dashboard"))

        rag_service = RAGService(app)
        try:
            storage_filename = rag_service.delete_document(document_id=document_id)
            if storage_filename is None:
                flash("Document not found.", "warning")
            else:
                if storage_filename:
                    storage_path = os.path.join(app.config["UPLOAD_FOLDER"], storage_filename)
                    if os.path.exists(storage_path):
                        os.remove(storage_path)
                flash("Document deleted successfully.", "success")
        except Exception as exc:
            flash(f"Document deletion failed: {exc}", "danger")

        return redirect(url_for("admin_dashboard"))

    @app.route("/user")
    @login_required
    def user_dashboard():
        if current_user.role != "user":
            flash("Access denied.", "danger")
            return redirect(url_for("admin_dashboard"))

        rag_service = RAGService(app)
        subjects = rag_service.get_subjects()
        return render_template("user_dashboard.html", subjects=subjects)

    @app.route("/user/ask", methods=["POST"])
    @login_required
    def ask_question():
        if current_user.role != "user":
            return jsonify(error="Access denied."), 403

        subject = request.form.get("subject", "").strip()
        question = request.form.get("question", "").strip()

        if not subject or not question:
            return jsonify(error="Please select a subject and enter a question."), 400

        try:
            rag_service = RAGService(app)
            answer = rag_service.answer_question(question=question, subject=subject)
            return jsonify(subject=subject, question=question, answer=answer)
        except Exception:
            app.logger.exception("Question answering failed for user %s", current_user.id)
            return jsonify(error="Unable to answer right now. Please try again."), 500

    return app
