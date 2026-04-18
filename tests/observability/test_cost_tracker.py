from src.observability.cost_tracker import CostTracker


class TestCostTracker:
    def setup_method(self):
        self.ct = CostTracker(filename="test_costs.jsonl")
        self.ct.reset()

    def teardown_method(self):
        self.ct.reset()

    def test_record_and_get_spend(self):
        self.ct.record_cost("task-1", "Ideator", 0.005)
        assert self.ct.get_task_spend("task-1") == 0.005
        assert self.ct.get_total_spend() == 0.005

    def test_multiple_agents_same_task(self):
        self.ct.record_cost("task-1", "Ideator", 0.005)
        self.ct.record_cost("task-1", "Builder", 0.003)
        assert self.ct.get_task_spend("task-1") == 0.008

    def test_persistence(self):
        self.ct.record_cost("task-1", "Ideator", 0.005)
        ct2 = CostTracker(filename="test_costs.jsonl")
        assert ct2.get_total_spend() == 0.005
        ct2.reset()
