"""IntentRouter — turns a thought seed into a summoned agent name."""

from terramon.ports.classifier_port import ClassifierPort


class IntentRouter:
    """Primary adapter wrapper that routes player input to an agent."""

    def __init__(self, classifier: ClassifierPort) -> None:
        """Inject a classifier port."""
        self.classifier = classifier

    def route(self, thought_seed: str) -> str:
        """Return the agent name best suited to handle the input."""
        return self.classifier.classify(thought_seed)
