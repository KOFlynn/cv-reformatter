"""The two ways a labelling request can fail that are not the model's fault,
so are not a labelling failure. A labelling failure (the model answered, but
unusably) completes the job with every block in the review appendix; these
two stop the job instead, because the fault is not in the CV and the
appendix would say that it was.

``ProviderUnavailable``: the provider could not be reached, or was rate
limiting or overloaded, and still was after the provider client's own
retries. Transient: the caller should try again later (the API answers 503).

``LabellerMisconfigured``: the provider rejected the request itself (bad
key, no access, unknown model, invalid request) or the configuration names
a provider with no support. Not transient: the operator must fix the
configuration.

Anything else raised while labelling is a defect and is left to propagate.
"""

__all__ = ["LabellerError", "LabellerMisconfigured", "ProviderUnavailable"]


class LabellerError(Exception):
    """Base for a labelling request that stopped the job."""


class ProviderUnavailable(LabellerError):
    """The provider was unreachable, rate limiting or overloaded after
    retries. Try again later."""


class LabellerMisconfigured(LabellerError):
    """The provider rejected the request because of how the labeller is
    configured. Fix the configuration; retrying will not help."""
