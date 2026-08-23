from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class Role:
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"

    ALL = [SUPER_ADMIN, ADMIN, MANAGER, EMPLOYEE]
    LABELS = {
        SUPER_ADMIN: "Super Admin",
        ADMIN: "Admin",
        MANAGER: "Manager",
        EMPLOYEE: "Employee",
    }
    ADMIN_ROLES = [SUPER_ADMIN, ADMIN]


class TicketStatus:
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting_response"
    RESOLVED = "resolved"
    CLOSED = "closed"

    ORDER = [OPEN, IN_PROGRESS, WAITING, RESOLVED, CLOSED]
    LABELS = {
        OPEN: "Open",
        IN_PROGRESS: "In Progress",
        WAITING: "Waiting for Response",
        RESOLVED: "Resolved",
        CLOSED: "Closed",
    }
    ACTIVE = [OPEN, IN_PROGRESS, WAITING]


class TicketPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

    ORDER = [LOW, MEDIUM, HIGH, URGENT]
    LABELS = {LOW: "Low", MEDIUM: "Medium", HIGH: "High", URGENT: "Urgent"}
    WEIGHT = {LOW: 1, MEDIUM: 2, HIGH: 3, URGENT: 4}


class NotificationType:
    ASSIGNED = "ticket_assigned"
    NEW_REPLY = "new_reply"
    STATUS_CHANGED = "status_changed"
    REASSIGNED = "reassigned"
    NEW_TICKET = "new_ticket"
    MENTION = "mention"


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(500))
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id", use_alter=True, name="fk_department_manager"))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    manager = db.relationship("User", foreign_keys=[manager_id], post_update=True)
    members = db.relationship("User", foreign_keys="User.department_id", back_populates="department")

    def member_count(self):
        return sum(1 for m in self.members if m.is_active)

    def open_ticket_count(self):
        return Ticket.query.filter(
            Ticket.department_id == self.id,
            Ticket.status.in_(TicketStatus.ACTIVE),
        ).count()

    def __repr__(self):
        return f"<Department {self.name}>"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Category {self.name}>"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.EMPLOYEE)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active_at = db.Column(db.DateTime)

    department = db.relationship("Department", foreign_keys=[department_id], back_populates="members")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def touch_activity(self):
        self.last_active_at = datetime.utcnow()

    @property
    def initials(self):
        parts = self.name.split()
        letters = "".join(p[0] for p in parts[:2] if p)
        return letters.upper() or "U"

    @property
    def avatar_color(self):
        palette = ["#2563eb", "#7c3aed", "#0891b2", "#059669", "#d97706", "#dc2626", "#4f46e5"]
        return palette[self.id % len(palette)] if self.id else palette[0]

    def is_admin_like(self):
        return self.role in Role.ADMIN_ROLES

    def can_manage_department(self, department_id):
        if self.is_admin_like():
            return True
        return self.role == Role.MANAGER and self.department_id == department_id

    def unread_notification_count(self):
        return Notification.query.filter_by(user_id=self.id, is_read=False).count()

    def __repr__(self):
        return f"<User {self.email}>"


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    priority = db.Column(db.String(20), nullable=False, default=TicketPriority.MEDIUM)
    status = db.Column(db.String(30), nullable=False, default=TicketStatus.OPEN)

    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    category = db.relationship("Category")
    creator = db.relationship("User", foreign_keys=[creator_id])
    recipient_user = db.relationship("User", foreign_keys=[recipient_user_id])
    department = db.relationship("Department", foreign_keys=[department_id], backref="tickets")
    assignee = db.relationship("User", foreign_keys=[assignee_id])

    messages = db.relationship(
        "TicketMessage", back_populates="ticket", order_by="TicketMessage.created_at",
        cascade="all, delete-orphan",
    )

    @property
    def ticket_number(self):
        return f"#{1000 + self.id}"

    @property
    def status_label(self):
        return TicketStatus.LABELS.get(self.status, self.status)

    @property
    def priority_label(self):
        return TicketPriority.LABELS.get(self.priority, self.priority)

    def is_open_state(self):
        return self.status in TicketStatus.ACTIVE

    def can_view(self, user):
        if user.is_admin_like():
            return True
        if user.id in (self.creator_id, self.recipient_user_id, self.assignee_id):
            return True
        if user.role == Role.MANAGER and user.department_id == self.department_id:
            return True
        if self.department_id and user.department_id == self.department_id:
            return True
        return False

    def can_manage(self, user):
        """Change status/priority/assignment/close."""
        if user.is_admin_like():
            return True
        if user.id == self.assignee_id:
            return True
        if user.role == Role.MANAGER and user.department_id == self.department_id:
            return True
        return False

    def last_message_at(self):
        if self.messages:
            return self.messages[-1].created_at
        return self.created_at

    def __repr__(self):
        return f"<Ticket {self.ticket_number} {self.title!r}>"


class TicketMessage(db.Model):
    __tablename__ = "ticket_messages"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_internal_note = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship("Ticket", back_populates="messages")
    sender = db.relationship("User")
    attachments = db.relationship(
        "TicketAttachment", back_populates="message", cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<TicketMessage ticket={self.ticket_id} sender={self.sender_id}>"


class TicketAttachment(db.Model):
    __tablename__ = "ticket_attachments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    message_id = db.Column(db.Integer, db.ForeignKey("ticket_messages.id"))
    uploader_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(120))
    size_bytes = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship("Ticket")
    message = db.relationship("TicketMessage", back_populates="attachments")
    uploader = db.relationship("User")

    @property
    def is_image(self):
        ext = self.original_filename.rsplit(".", 1)[-1].lower() if "." in self.original_filename else ""
        return ext in {"png", "jpg", "jpeg", "gif", "webp"}

    def human_size(self):
        size = self.size_bytes or 0
        for unit in ("B", "KB", "MB"):
            if size < 1024:
                return f"{size:.0f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.String(500))
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"))
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship("Ticket")

    def __repr__(self):
        return f"<Notification user={self.user_id} type={self.type}>"


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(60), nullable=False)
    target_type = db.Column(db.String(40))
    target_id = db.Column(db.Integer)
    description = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    actor = db.relationship("User")

    def __repr__(self):
        return f"<ActivityLog {self.action} by={self.actor_id}>"
