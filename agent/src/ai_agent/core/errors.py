"""Custom exceptions with proper error handling."""


class AIAgentError(Exception):
    """Base exception for all AI agent errors."""

    pass


class ConfigurationError(AIAgentError):
    """Configuration error."""

    pass


class AgentExecutionError(AIAgentError):
    """Agent execution error."""

    def __init__(self, agent_name: str, message: str, cause: Exception | None = None):
        self.agent_name = agent_name
        self.cause = cause
        super().__init__(f"Agent '{agent_name}' failed: {message}")


class ToolExecutionError(AIAgentError):
    """Tool execution error."""

    def __init__(self, tool_name: str, message: str, cause: Exception | None = None):
        self.tool_name = tool_name
        self.cause = cause
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class TimeoutError(AIAgentError):
    """Execution timeout error."""

    pass


class ValidationError(AIAgentError):
    """Input/output validation error."""

    pass
