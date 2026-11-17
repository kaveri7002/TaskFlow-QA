import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

db = SQLAlchemy()

ROOT_DIR = Path(__file__).resolve().parents[1]
ALLOWED_STATUSES = {"todo", "in_progress", "completed"}
ALLOWED_PRIORITIES = {"low", "medium", "high"}
TASK_FIELDS = {"title", "description", "status", "priority", "due_date"}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    tasks = db.relationship("Task", back_populates="user", cascade="all, delete-orphan")


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(2000), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="todo", index=True)
    priority = db.Column(db.String(10), nullable=False, default="medium", index=True)
    due_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", back_populates="tasks")

    def as_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def _database_url():
    default_database = (ROOT_DIR / "database" / "taskflow-local.db").as_posix()
    url = os.getenv("DATABASE_URL", f"sqlite:///{default_database}")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_app(test_config=None):
    configured_secret = os.getenv("SECRET_KEY")
    local_debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    is_test = bool(test_config and test_config.get("TESTING"))
    if not configured_secret and not local_debug and not is_test:
        raise RuntimeError("Set SECRET_KEY to a persistent random value before starting TaskFlow QA.")

    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=configured_secret or "local-test-secret-change-before-deploying",
        SQLALCHEMY_DATABASE_URI=_database_url(),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TOKEN_MAX_AGE_SECONDS=int(os.getenv("TOKEN_MAX_AGE_SECONDS", "86400")),
        FRONTEND_DIST_DIR=str(ROOT_DIR / "frontend"),
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    origins = [
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
    CORS(app, resources={r"/api/*": {"origins": origins}}, allow_headers=["Content-Type", "Authorization"])

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "The requested resource was not found."}), 404
        return jsonify({"error": "Page not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "This HTTP method is not allowed for this resource."}), 405

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error("Unhandled server error: %s", error)
        return jsonify({"error": "An unexpected server error occurred."}), 500

    def serializer():
        return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="taskflow-auth-v1")

    def current_user():
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        try:
            user_id = serializer().loads(
                token,
                max_age=app.config["TOKEN_MAX_AGE_SECONDS"],
            )
        except (BadSignature, SignatureExpired):
            return None
        return db.session.get(User, user_id)

    def require_user():
        user = current_user()
        if user is None:
            return None, (jsonify({"error": "Sign in to continue."}), 401)
        return user, None

    def json_object():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return None, (jsonify({"error": "Send a valid JSON object."}), 400)
        return payload, None

    def serialize_user(user, token):
        return {
            "token": token,
            "user": {"id": user.id, "name": user.name, "email": user.email},
        }

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.post("/api/auth/register")
    def register():
        payload, error = json_object()
        if error:
            return error

        name = payload.get("name", "").strip() if isinstance(payload.get("name", ""), str) else ""
        email = payload.get("email", "").strip().lower() if isinstance(payload.get("email", ""), str) else ""
        password = payload.get("password", "")
        if not name or len(name) > 80:
            return jsonify({"error": "Name is required and must be 80 characters or fewer."}), 400
        if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return jsonify({"error": "Enter a valid email address."}), 400
        if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
            return jsonify({"error": "Password must be between 8 and 128 characters."}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "An account with that email already exists."}), 409

        user = User(name=name, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        token = serializer().dumps(user.id)
        return jsonify(serialize_user(user, token)), 201

    @app.post("/api/auth/login")
    def login():
        payload, error = json_object()
        if error:
            return error
        email = payload.get("email", "").strip().lower() if isinstance(payload.get("email", ""), str) else ""
        password = payload.get("password", "")
        user = User.query.filter_by(email=email).first() if email else None
        if not user or not isinstance(password, str) or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Email or password is incorrect."}), 401
        token = serializer().dumps(user.id)
        return jsonify(serialize_user(user, token))

    @app.get("/api/auth/me")
    def me():
        user, error = require_user()
        if error:
            return error
        return jsonify({"user": {"id": user.id, "name": user.name, "email": user.email}})

    @app.get("/api/tasks")
    def list_tasks():
        user, error = require_user()
        if error:
            return error
        query = Task.query.filter_by(user_id=user.id)
        search = request.args.get("search", "").strip()
        status = request.args.get("status", "").strip()
        priority = request.args.get("priority", "").strip()
        if search:
            pattern = f"%{search}%"
            query = query.filter(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
        if status:
            if status not in ALLOWED_STATUSES:
                return jsonify({"error": "Choose a valid task status."}), 400
            query = query.filter_by(status=status)
        if priority:
            if priority not in ALLOWED_PRIORITIES:
                return jsonify({"error": "Choose a valid task priority."}), 400
            query = query.filter_by(priority=priority)
        tasks = query.order_by(Task.created_at.desc()).limit(200).all()
        return jsonify({"tasks": [task.as_dict() for task in tasks]})

    def validate_task_values(payload, partial=False):
        if not isinstance(payload, dict):
            return None, "Send a valid JSON object."
        if partial and not payload:
            return None, "Provide at least one task field to update."
        if set(payload) - TASK_FIELDS:
            return None, "One or more task fields are not supported."
        values = {}
        if not partial or "title" in payload:
            title = payload.get("title")
            if not isinstance(title, str) or not title.strip() or len(title.strip()) > 160:
                return None, "Task title is required and must be 160 characters or fewer."
            values["title"] = title.strip()
        if not partial or "description" in payload:
            description = payload.get("description", "")
            if not isinstance(description, str) or len(description) > 2000:
                return None, "Description must be 2,000 characters or fewer."
            values["description"] = description.strip()
        if not partial or "status" in payload:
            status = payload.get("status", "todo")
            if not isinstance(status, str) or status not in ALLOWED_STATUSES:
                return None, "Choose To do, In progress, or Completed."
            values["status"] = status
        if not partial or "priority" in payload:
            priority = payload.get("priority", "medium")
            if not isinstance(priority, str) or priority not in ALLOWED_PRIORITIES:
                return None, "Choose Low, Medium, or High priority."
            values["priority"] = priority
        if not partial or "due_date" in payload:
            raw_date = payload.get("due_date")
            if raw_date in (None, ""):
                values["due_date"] = None
            elif not isinstance(raw_date, str):
                return None, "Due date must use YYYY-MM-DD format."
            else:
                try:
                    values["due_date"] = date.fromisoformat(raw_date)
                except ValueError:
                    return None, "Due date must use YYYY-MM-DD format."
        return values, None

    @app.post("/api/tasks")
    def create_task():
        user, error = require_user()
        if error:
            return error
        payload, error = json_object()
        if error:
            return error
        values, validation_error = validate_task_values(payload)
        if validation_error:
            return jsonify({"error": validation_error}), 400
        task = Task(user_id=user.id, **values)
        db.session.add(task)
        db.session.commit()
        return jsonify({"task": task.as_dict()}), 201

    def owned_task(task_id, user):
        return Task.query.filter_by(id=task_id, user_id=user.id).first()

    @app.route("/api/tasks/<int:task_id>", methods=["PUT", "PATCH"])
    def update_task(task_id):
        user, error = require_user()
        if error:
            return error
        task = owned_task(task_id, user)
        if not task:
            return jsonify({"error": "Task not found."}), 404
        payload, error = json_object()
        if error:
            return error
        values, validation_error = validate_task_values(payload, partial=request.method == "PATCH")
        if validation_error:
            return jsonify({"error": validation_error}), 400
        for field, value in values.items():
            setattr(task, field, value)
        task.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({"task": task.as_dict()})

    @app.delete("/api/tasks/<int:task_id>")
    def delete_task(task_id):
        user, error = require_user()
        if error:
            return error
        task = owned_task(task_id, user)
        if not task:
            return jsonify({"error": "Task not found."}), 404
        db.session.delete(task)
        db.session.commit()
        return jsonify({"message": "Task deleted."})

    frontend_dir = Path(app.config["FRONTEND_DIST_DIR"])

    @app.get("/")
    def frontend_index():
        if (frontend_dir / "index.html").is_file():
            return send_from_directory(frontend_dir, "index.html")
        return jsonify({"message": "TaskFlow QA API and frontend are running."})

    @app.get("/<path:asset_path>")
    def frontend_assets(asset_path):
        if asset_path.startswith("api/"):
            return jsonify({"error": "The requested resource was not found."}), 404
        requested = frontend_dir / asset_path
        if requested.is_file():
            return send_from_directory(frontend_dir, asset_path)
        if (frontend_dir / "index.html").is_file():
            return send_from_directory(frontend_dir, "index.html")
        return jsonify({"error": "Frontend files are not available."}), 404

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
