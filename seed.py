"""Seed realistic development data for Saipa Mashayekh 3299.

Usage:
    python seed.py           # wipes and recreates all tables, then seeds
    python seed.py --keep    # seeds without dropping existing tables (skips if data exists)
"""

import sys
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import (
    User, Department, Category, Ticket, TicketMessage, Notification, ActivityLog,
    Role, TicketStatus, TicketPriority, NotificationType,
)

DEMO_PASSWORD = "Demo@12345"
ADMIN_PASSWORD = "Admin@12345"


def seed():
    app = create_app()
    with app.app_context():
        keep = "--keep" in sys.argv
        if keep and User.query.first():
            print("Data already present, skipping seed (--keep).")
            return

        db.drop_all()
        db.create_all()

        # ---------------------------------------------------------- Departments
        dept_names = [
            ("Management", "Executive leadership and company-wide coordination."),
            ("Sales", "Vehicle sales, dealer relations, and customer acquisition."),
            ("Finance", "Budgeting, payroll, invoicing, and financial reporting."),
            ("IT", "Internal systems, hardware, and technical support."),
            ("Human Resources", "Hiring, employee relations, and internal policy."),
            ("Procurement", "Supplier sourcing, purchasing, and vendor contracts."),
            ("Customer Support", "Post-sale customer service and issue resolution."),
        ]
        departments = {}
        for name, desc in dept_names:
            d = Department(name=name, description=desc)
            db.session.add(d)
            departments[name] = d
        db.session.flush()

        # -------------------------------------------------------------- Categories
        category_names = [
            "Administrative", "IT Support", "Sales", "Finance",
            "Human Resources", "Management", "Procurement", "Customer Support", "Other",
        ]
        for name in category_names:
            db.session.add(Category(name=name))
        db.session.flush()
        categories = {c.name: c for c in Category.query.all()}

        # ------------------------------------------------------------------- Users
        def make_user(name, email, role, department, password=DEMO_PASSWORD):
            u = User(name=name, email=email, role=role, department_id=department.id if department else None)
            u.set_password(password)
            u.last_active_at = datetime.utcnow() - timedelta(hours=len(name))
            db.session.add(u)
            return u

        super_admin = make_user("Mohammad Saipa", "admin@saipamashayekh.local", Role.SUPER_ADMIN,
                                 departments["Management"], ADMIN_PASSWORD)
        it_admin = make_user("Leila Ahmadi", "leila.ahmadi@saipamashayekh.local", Role.ADMIN, departments["IT"])

        sales_manager = make_user("Sara Karimi", "sara.karimi@saipamashayekh.local", Role.MANAGER, departments["Sales"])
        it_manager = make_user("Amir Tehrani", "amir.tehrani@saipamashayekh.local", Role.MANAGER, departments["IT"])
        finance_manager = make_user("Niloofar Rahimi", "niloofar.rahimi@saipamashayekh.local", Role.MANAGER, departments["Finance"])
        hr_manager = make_user("Hossein Moradi", "hossein.moradi@saipamashayekh.local", Role.MANAGER, departments["Human Resources"])
        procurement_manager = make_user("Zahra Hosseini", "zahra.hosseini@saipamashayekh.local", Role.MANAGER, departments["Procurement"])
        support_manager = make_user("Kaveh Jafari", "kaveh.jafari@saipamashayekh.local", Role.MANAGER, departments["Customer Support"])

        employees = [
            make_user("Ali Rezaei", "ali.rezaei@saipamashayekh.local", Role.EMPLOYEE, departments["Sales"]),
            make_user("Fatemeh Ghasemi", "fatemeh.ghasemi@saipamashayekh.local", Role.EMPLOYEE, departments["Finance"]),
            make_user("Omid Salehi", "omid.salehi@saipamashayekh.local", Role.EMPLOYEE, departments["IT"]),
            make_user("Maryam Sadeghi", "maryam.sadeghi@saipamashayekh.local", Role.EMPLOYEE, departments["Human Resources"]),
            make_user("Reza Norouzi", "reza.norouzi@saipamashayekh.local", Role.EMPLOYEE, departments["Procurement"]),
            make_user("Yasaman Bagheri", "yasaman.bagheri@saipamashayekh.local", Role.EMPLOYEE, departments["Customer Support"]),
            make_user("Kian Mousavi", "kian.mousavi@saipamashayekh.local", Role.EMPLOYEE, departments["Sales"]),
        ]
        db.session.flush()

        departments["Management"].manager_id = super_admin.id
        departments["IT"].manager_id = it_manager.id
        departments["Sales"].manager_id = sales_manager.id
        departments["Finance"].manager_id = finance_manager.id
        departments["Human Resources"].manager_id = hr_manager.id
        departments["Procurement"].manager_id = procurement_manager.id
        departments["Customer Support"].manager_id = support_manager.id
        db.session.flush()

        ali, fatemeh, omid, maryam, reza_n, yasaman, kian = employees

        # ------------------------------------------------------------------ Tickets
        def make_ticket(creator, title, description, category_name, priority, status,
                         recipient_user=None, recipient_department=None, assignee=None,
                         days_ago=0, conversation=None):
            ticket = Ticket(
                title=title, description=description,
                category_id=categories[category_name].id, priority=priority, status=status,
                creator_id=creator.id,
                recipient_user_id=recipient_user.id if recipient_user else None,
                department_id=(recipient_department.id if recipient_department else
                               (recipient_user.department_id if recipient_user else None)),
                assignee_id=assignee.id if assignee else (recipient_user.id if recipient_user else
                            (recipient_department.manager_id if recipient_department else None)),
            )
            created_at = datetime.utcnow() - timedelta(days=days_ago, hours=2)
            ticket.created_at = created_at
            ticket.updated_at = created_at
            db.session.add(ticket)
            db.session.flush()

            db.session.add(TicketMessage(ticket_id=ticket.id, sender_id=creator.id, body=description,
                                          created_at=created_at))

            if conversation:
                for i, (sender, body, is_note) in enumerate(conversation, start=1):
                    msg_time = created_at + timedelta(hours=i * 3)
                    db.session.add(TicketMessage(ticket_id=ticket.id, sender_id=sender.id, body=body,
                                                  is_internal_note=is_note, created_at=msg_time))
                    ticket.updated_at = msg_time

            if status == TicketStatus.RESOLVED:
                ticket.resolved_at = ticket.updated_at
            if status == TicketStatus.CLOSED:
                ticket.resolved_at = ticket.updated_at
                ticket.closed_at = ticket.updated_at

            recipients = [recipient_user] if recipient_user else (
                [recipient_department.manager] if recipient_department and recipient_department.manager else []
            )
            for r in recipients:
                db.session.add(Notification(
                    user_id=r.id, type=NotificationType.NEW_TICKET,
                    title=f"New request: {ticket.ticket_number}", body=title,
                    ticket_id=ticket.id, is_read=(status not in TicketStatus.ACTIVE), created_at=created_at,
                ))

            db.session.add(ActivityLog(
                actor_id=creator.id, action="ticket_created",
                description=f"{creator.name} created ticket #{1000 + ticket.id}: \"{title}\"",
                target_type="ticket", target_id=ticket.id, created_at=created_at,
            ))
            return ticket

        make_ticket(
            kian, "Computer in Sales department not booting",
            "Hello, the computer in the sales department is having a problem starting up this morning.",
            "IT Support", TicketPriority.HIGH, TicketStatus.WAITING,
            recipient_department=departments["IT"], assignee=it_manager, days_ago=2,
            conversation=[
                (it_manager, "Hello. I checked the issue. Please restart the computer and let me know if the problem continues.", False),
                (kian, "I restarted it, but the problem still exists.", False),
                (it_manager, "Understood — sounds like a power supply fault. I'll send a technician to your desk this afternoon.", False),
            ],
        )

        make_ticket(
            ali, "Approval needed for new laptop",
            "I need approval for new equipment — my current laptop is over 4 years old and struggling to run our CRM.",
            "Procurement", TicketPriority.MEDIUM, TicketStatus.IN_PROGRESS,
            recipient_department=departments["Procurement"], assignee=procurement_manager, days_ago=4,
            conversation=[
                (procurement_manager, "Request received. We are checking available suppliers.", False),
                (ali, "Thank you. Please let me know when the quotation is available.", False),
                (procurement_manager, "Vendor quote received internally — awaiting budget sign-off.", True),
            ],
        )

        make_ticket(
            fatemeh, "Reimbursement for client dinner",
            "Please process my reimbursement for the client dinner on the 12th. Receipt attached in a follow-up message.",
            "Finance", TicketPriority.LOW, TicketStatus.RESOLVED,
            recipient_department=departments["Finance"], assignee=finance_manager, days_ago=9,
            conversation=[
                (finance_manager, "Received, thanks. Processing this with next week's payroll run.", False),
                (finance_manager, "This has been reimbursed — you should see it in your next paycheck.", False),
            ],
        )

        make_ticket(
            maryam, "Update emergency contact information",
            "I'd like to update my emergency contact information on file with HR.",
            "Human Resources", TicketPriority.LOW, TicketStatus.CLOSED,
            recipient_department=departments["Human Resources"], assignee=hr_manager, days_ago=14,
            conversation=[
                (hr_manager, "Updated on our end — thanks for letting us know!", False),
            ],
        )

        make_ticket(
            omid, "VPN access request for remote work",
            "Requesting VPN credentials to work remotely next week for a family matter.",
            "IT Support", TicketPriority.URGENT, TicketStatus.OPEN,
            recipient_user=it_admin, days_ago=0,
        )

        make_ticket(
            yasaman, "Customer complaint escalation — Order #48213",
            "A customer is unhappy about a delayed delivery and is asking to speak with a manager. Escalating for visibility.",
            "Customer Support", TicketPriority.URGENT, TicketStatus.IN_PROGRESS,
            recipient_department=departments["Customer Support"], assignee=support_manager, days_ago=1,
            conversation=[
                (support_manager, "Thanks for flagging — I'll call the customer directly within the hour.", False),
            ],
        )

        make_ticket(
            reza_n, "New supplier onboarding checklist",
            "Could Procurement share the current supplier onboarding checklist? We have a new parts vendor to bring on.",
            "Procurement", TicketPriority.MEDIUM, TicketStatus.OPEN,
            recipient_department=departments["Procurement"], assignee=procurement_manager, days_ago=0,
        )

        make_ticket(
            sales_manager, "Quarterly sales dashboard access",
            "Could IT grant our new hires access to the quarterly sales dashboard?",
            "IT Support", TicketPriority.MEDIUM, TicketStatus.WAITING,
            recipient_department=departments["IT"], assignee=it_manager, days_ago=3,
            conversation=[
                (it_manager, "Sure — please send me the list of names and I'll set up accounts today.", False),
            ],
        )

        make_ticket(
            ali, "Printer out of toner — 3rd floor",
            "The printer near the sales bullpen on the 3rd floor is out of toner.",
            "Administrative", TicketPriority.LOW, TicketStatus.CLOSED,
            recipient_department=departments["IT"], assignee=it_admin, days_ago=20,
            conversation=[(it_admin, "Replaced the toner cartridge this morning.", False)],
        )

        make_ticket(
            kian, "Password reset for internal CRM",
            "I'm locked out of the CRM after too many failed login attempts.",
            "IT Support", TicketPriority.HIGH, TicketStatus.RESOLVED,
            recipient_user=it_admin, days_ago=1,
            conversation=[(it_admin, "Reset your password — check your email for the temporary credentials.", False)],
        )

        db.session.commit()

        print("Seed complete.")
        print(f"  Super Admin login: admin@saipamashayekh.local / {ADMIN_PASSWORD}")
        print(f"  All other seeded users share the password: {DEMO_PASSWORD}")
        print("  e.g. sara.karimi@saipamashayekh.local (Sales Manager), ali.rezaei@saipamashayekh.local (Employee)")


if __name__ == "__main__":
    seed()
