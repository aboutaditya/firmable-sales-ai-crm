import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sales_intelligence.models import Base, CallActivity, Company, CompanyAssignment, CompanySignal
from sales_intelligence.repositories import PostgresCompanyRepository, PostgresQueueRepository


class QueueRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.catalog = PostgresCompanyRepository(self.session_factory)
        self.repository = PostgresQueueRepository(self.session_factory)
        with self.session_factory.begin() as session:
            session.add_all([
                Company(id="high.example", domain="high.example", organization="High Co", security_score=85, score_version="v1", dataset_version="demo"),
                Company(id="medium.example", domain="medium.example", organization="Medium Co", security_score=70, score_version="v1", dataset_version="demo"),
                Company(id="low.example", domain="low.example", organization="Low Co", security_score=45, score_version="v1", dataset_version="demo"),
                Company(id="fresh.example", domain="fresh.example", organization="Fresh Co", security_score=30, score_version="v1", dataset_version="demo"),
                CompanySignal(company_id="high.example", vulnerability_count=4, critical_vulnerability_count=1),
                CompanySignal(company_id="medium.example", vulnerability_count=2),
                CompanySignal(company_id="low.example", vulnerability_count=1),
                CompanySignal(company_id="fresh.example", vulnerability_count=0),
                CompanyAssignment(company_id="high.example", user_id="alice", assigned_by="manager"),
                CompanyAssignment(company_id="low.example", user_id="alice", assigned_by="manager"),
                CompanyAssignment(company_id="high.example", user_id="bob", assigned_by="manager"),
            ])

    def test_next_claims_highest_unassigned_company(self):
        users = self.repository.list_queue_users()
        self.assertEqual({item["user_id"] for item in users}, {"alice", "bob"})
        status = self.repository.queue_status("alice")
        self.assertEqual(status["assigned_count"], 2)
        self.assertEqual(status["eligible_count"], 2)

        lead = self.repository.next_assigned_company("alice")
        self.assertEqual(lead["company"]["company_id"], "medium.example")
        self.assertEqual(lead["status"], "in_progress")
        status = self.repository.queue_status("alice")
        self.assertEqual(status["assigned_count"], 3)
        self.assertEqual(status["eligible_count"], 1)

        self.assertIsNone(self.catalog.get_company("medium.example", user_id="bob", role="sales_rep"))
        self.assertIsNotNone(self.catalog.get_company("high.example", user_id="bob", role="sales_rep"))
        self.repository.update_preferences("alice", min_exposure_score=90)
        self.assertEqual(self.repository.next_assigned_company("alice")["company"]["company_id"], "fresh.example")

    def test_list_assigned_companies(self):
        self.repository.next_assigned_company("alice")
        leads, total = self.repository.list_assigned_companies("alice")
        ids = [lead["company"]["company_id"] for lead in leads]
        self.assertEqual(total, 3)
        self.assertEqual(ids, ["medium.example", "high.example", "low.example"])

        page1, total = self.repository.list_assigned_companies("alice", limit=2, offset=0)
        self.assertEqual([lead["company"]["company_id"] for lead in page1], ["medium.example", "high.example"])
        self.assertEqual(total, 3)
        page2, _ = self.repository.list_assigned_companies("alice", limit=2, offset=2)
        self.assertEqual([lead["company"]["company_id"] for lead in page2], ["low.example"])

    def test_disposition_and_call_activity_change_queue_state(self):
        lead = self.repository.next_assigned_company("alice")
        updated = self.repository.update_disposition(
            lead["company"]["company_id"],
            "alice",
            disposition="qualified",
            notes="Confirmed a security review is timely.",
            next_follow_up_at=None,
        )
        self.assertEqual(updated["status"], "completed")

        next_lead = self.repository.next_assigned_company("alice")
        self.assertEqual(next_lead["company"]["company_id"], "fresh.example")
        call = self.repository.record_call(
            "fresh.example",
            "alice",
            outcome="call_attempted",
            notes="Left voicemail.",
            next_follow_up_at=datetime.now(timezone.utc),
        )
        self.assertEqual(call["status"], "in_progress")
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(CallActivity)), 1)


if __name__ == "__main__":
    unittest.main()
