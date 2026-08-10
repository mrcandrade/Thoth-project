"""Smoke test do workflow."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_workflow():
    from workflow_jokenpo_robotico import fluxo
    assert fluxo is not None
    assert len(fluxo.steps) == 5


if __name__ == "__main__":
    test_workflow()
    print("OK: workflow instancia com", len(__import__("workflow_jokenpo_robotico").fluxo.steps), "steps")
