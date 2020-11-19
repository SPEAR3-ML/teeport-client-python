class TaskStopped(Exception):
    """Thrown when a task is stopped abnormally.

    """
    pass

class OptimizerStopped(Exception):
    """Thrown when the optimizer crashes.

    """
    pass

class Disconnected(Exception):
    """Thrown when the Teeport node is disconnected abnormally.

    """
    pass
