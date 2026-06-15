from agents.lead_workflow.distributed.agent_server import create_agent_service_app

app = create_agent_service_app()

__all__ = ["app"]
